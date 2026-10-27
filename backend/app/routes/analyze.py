from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..models.schemas import (
    AnalyzeResponse,
    ConfigResponse,
    ExtractedEntities,
    HealthResponse,
    Improvement,
    MissingRequirement,
    Priority,
    PrivacyInfo,
    RoleResponse,
    ScoreBand,
    ScoringSource,
)
from ..services.llm_scorer import LLMOutcome
from ..services.matcher import MatchResult
from ..services.rate_limit import client_ip
from ..services.resume_parser import (
    DocumentError,
    ScannedDocumentError,
    UnreadableDocumentError,
    UnsupportedDocumentError,
    parse_document,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid.uuid4().hex[:12])


def _band_for(score: float) -> ScoreBand:
    if score >= 8:
        return ScoreBand.EXCELLENT
    if score >= 6:
        return ScoreBand.GOOD
    if score >= 4:
        return ScoreBand.MODERATE
    return ScoreBand.NEEDS_WORK


def _merge_llm(
    local: MatchResult,
    llm: LLMOutcome,
    *,
    extracted: ExtractedEntities,
    embedding_model: str,
    consent: bool,
    settings: Settings,
) -> AnalyzeResponse:
    improvements: list[Improvement] = []
    seen: set[str] = set()
    for gap in llm.missing:
        key = gap.lower()
        if key not in seen:
            seen.add(key)
            improvements.append(
                Improvement(
                    area=gap,
                    priority=Priority.HIGH,
                    action=f"Add concrete evidence of {gap.lower()} with scope and a measurable result.",
                )
            )
    for local_improvement in local.improvements:
        if local_improvement.area.lower() not in seen:
            seen.add(local_improvement.area.lower())
            improvements.append(local_improvement)

    missing = list(local.missing_requirements)
    known = {item.requirement.lower() for item in missing}
    for gap in llm.missing:
        if gap.lower() not in known:
            missing.append(
                MissingRequirement(
                    requirement=gap,
                    weight=2,
                    must_have=False,
                    why="Identified as a gap by the AI reviewer",
                )
            )

    evidence = list(llm.evidence)
    known_evidence = {item.requirement.lower() for item in evidence}
    for local_evidence in local.evidence:
        if local_evidence.requirement.lower() not in known_evidence:
            evidence.append(local_evidence)

    alternatives = llm.alternative_roles or local.alternative_roles
    score = llm.score
    return AnalyzeResponse(
        request_id="",  # filled by the route
        score=score,
        band=_band_for(score),
        matched_role=local.matched_role,
        alternative_roles=alternatives,
        improvements=improvements[:5],
        extracted_entities=extracted,
        rubric=local.rubric,
        evidence=evidence[:8],
        missing_requirements=missing,
        next_band_actions=local.next_band_actions,
        scoring_source=ScoringSource.OPENCODE_GO,
        llm_model=llm.model,
        embedding_model=embedding_model,
        jd_used=local.jd_used,
        privacy=PrivacyInfo(
            llm_enabled=settings.llm_configured,
            consent_given=consent,
            external_llm_used=True,
            retention_note=(
                "Rendered resume text is redacted and sent to OpenCode Go. "
                + (
                    "Beam Free retains prompts for 30 days for safety and does not train on them."
                    if llm.model == "beam-free"
                    else (
                        f"{llm.model} retains prompts according to its provider policy; see the privacy note."
                    )
                )
            ),
        ),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    target_role: Annotated[str, Form(min_length=2, max_length=100)],
    job_description: Annotated[str | None, Form()] = None,
    consent: Annotated[bool, Form()] = False,
) -> AnalyzeResponse:
    settings: Settings = _settings(request)
    request_id = _request_id(request)
    state = request.app.state

    target_role = target_role.strip()
    if len(target_role) < 2:
        raise HTTPException(status_code=400, detail="Choose a target role with at least two characters.")

    jd_text = (job_description or "").strip() or None
    if jd_text and len(jd_text) > settings.max_jd_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Job descriptions are limited to {settings.max_jd_chars:,} characters.",
        )

    allowed, retry_after = state.rate_limiter.check(client_ip(request, settings.trust_proxy_headers))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many analyses from this network. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    total = 0
    chunks: list[bytes] = []
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum {settings.max_upload_mb} MB allowed.",
                )
            chunks.append(chunk)
        file_bytes = b"".join(chunks)
    finally:
        await file.close()

    try:
        document = await run_in_threadpool(
            parse_document,
            file_bytes,
            file.filename,
            content_type=file.content_type,
            max_pages=settings.max_pages,
        )
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ScannedDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnreadableDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if document.is_scanned or len(document.text) < 50:
        raise HTTPException(
            status_code=422,
            detail=(
                "This file has no extractable resume text. If it is a scanned PDF, "
                "export a text-based PDF or DOCX and try again."
            ),
        )

    try:
        nlp = await run_in_threadpool(state.nlp_analyzer.analyze, document.text, document.lines)
        local = await run_in_threadpool(
            state.matcher.match,
            document.text,
            document.lines,
            nlp,
            target_role,
            jd_text,
        )
    except Exception as exc:
        logger.exception("Local analysis failed request_id=%s: %s", request_id, exc)
        raise HTTPException(status_code=500, detail="Analysis failed. Please retry.") from exc

    extracted = ExtractedEntities(
        skills=nlp.skills,
        skill_details=nlp.skill_details,
        education=nlp.education,
        experience_years=nlp.experience_years,
        experience_months=nlp.experience_months,
        resume_confidence=round(nlp.resume_confidence, 2),
        signals=nlp.signals,
    )

    llm_outcome: LLMOutcome | None = None
    scoring_source = ScoringSource.LOCAL_LLM_DISABLED
    if settings.llm_configured:
        if settings.require_consent and not consent:
            scoring_source = ScoringSource.LOCAL_CONSENT
        else:
            allowed_budget, reason = state.llm_budget.check()
            if not allowed_budget:
                scoring_source = ScoringSource.LOCAL_QUOTA
                logger.info("LLM budget guard hit request_id=%s reason=%s", request_id, reason)
            else:
                llm_outcome = await state.llm_scorer.score(
                    resume_text=document.text,
                    lines=document.lines,
                    target_role=target_role,
                    role_description=local.role_description,
                    skills=nlp.skills,
                    jd_text=jd_text,
                )
                if llm_outcome is not None:
                    state.llm_budget.record(llm_outcome.allowance_usd)
                    scoring_source = ScoringSource.OPENCODE_GO
                    if not llm_outcome.is_resume and nlp.resume_confidence < 0.5:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                "Uploaded document does not look like a candidate resume. "
                                "Upload a resume with experience, education, and skills."
                            ),
                        )
                else:
                    scoring_source = ScoringSource.LOCAL_FALLBACK

    if (
        llm_outcome is None
        and scoring_source
        in {
            ScoringSource.LOCAL,
            ScoringSource.LOCAL_FALLBACK,
            ScoringSource.LOCAL_LLM_DISABLED,
        }
        and nlp.resume_confidence < 0.3
        and len(nlp.skills) <= 2
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Uploaded document does not look like a candidate resume. "
                "Upload a resume with experience, education, and skills."
            ),
        )

    if llm_outcome is not None:
        response = _merge_llm(
            local,
            llm_outcome,
            extracted=extracted,
            embedding_model=state.embedder.name,
            consent=consent,
            settings=settings,
        )
    else:
        response = AnalyzeResponse(
            request_id="",
            score=local.score,
            band=local.band,
            matched_role=local.matched_role,
            alternative_roles=local.alternative_roles,
            improvements=local.improvements,
            extracted_entities=extracted,
            rubric=local.rubric,
            evidence=local.evidence,
            missing_requirements=local.missing_requirements,
            next_band_actions=local.next_band_actions,
            scoring_source=scoring_source,
            llm_model=None,
            embedding_model=state.embedder.name,
            jd_used=local.jd_used,
            privacy=PrivacyInfo(
                llm_enabled=settings.llm_configured,
                consent_given=consent,
                external_llm_used=False,
                retention_note="Processed in memory on this server; no upload is stored.",
            ),
        )

    response.request_id = request_id
    logger.info(
        "analysis request_id=%s source=%s score=%s role=%s jd=%s ext=%s bytes=%d skills=%d",
        request_id,
        scoring_source.value,
        response.score,
        response.matched_role,
        response.jd_used,
        document.source_format,
        total,
        len(nlp.skills),
    )
    return response


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    settings: Settings = _settings(request)
    embedder = getattr(request.app.state, "embedder", None)
    return HealthResponse(
        status="healthy",
        version=settings.version,
        ready=True,
        embedding_model=embedder.name if embedder is not None else None,
        llm_configured=settings.llm_configured,
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    settings: Settings = _settings(request)
    embedder = getattr(request.app.state, "embedder", None)
    matcher = getattr(request.app.state, "matcher", None)
    if embedder is None or matcher is None:
        raise HTTPException(status_code=503, detail="Models are still loading.")
    return HealthResponse(
        status="ready",
        version=settings.version,
        ready=True,
        embedding_model=embedder.name,
        llm_configured=settings.llm_configured,
    )


@router.get("/roles", response_model=RoleResponse)
async def get_roles(request: Request) -> RoleResponse:
    return RoleResponse(roles=[role.name for role in request.app.state.roles])


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request) -> ConfigResponse:
    settings: Settings = _settings(request)
    return ConfigResponse(
        llm_enabled=settings.llm_configured,
        llm_provider=settings.llm_provider,
        llm_model=settings.opencode_model,
        llm_fallback=settings.opencode_fallback_model,
        require_consent=settings.require_consent,
        max_upload_mb=settings.max_upload_mb,
        max_jd_chars=settings.max_jd_chars,
        version=settings.version,
    )
