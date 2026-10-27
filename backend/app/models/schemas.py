from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ScoreBand(StrEnum):
    EXCELLENT = "Excellent match"
    GOOD = "Good match"
    MODERATE = "Moderate match"
    NEEDS_WORK = "Needs work"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScoringSource(StrEnum):
    OPENCODE_GO = "opencode_go"
    LOCAL = "local"
    LOCAL_FALLBACK = "local_fallback"
    LOCAL_QUOTA = "local_quota"
    LOCAL_CONSENT = "local_consent"
    LOCAL_LLM_DISABLED = "local_llm_disabled"


class SkillEntity(BaseModel):
    name: str
    family: str
    mentions: int = 1


class ExtractedEntities(BaseModel):
    skills: list[str] = Field(default_factory=list)
    skill_details: list[SkillEntity] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience_years: float = 0.0
    experience_months: int = 0
    resume_confidence: float = 0.0
    signals: list[str] = Field(default_factory=list)


class Improvement(BaseModel):
    area: str
    priority: Priority
    action: str | None = None
    evidence: str | None = None


class RoleMatch(BaseModel):
    role: str
    match: float = Field(ge=0.0, le=1.0)
    match_kind: str = "semantic_similarity"


class EvidenceItem(BaseModel):
    requirement: str
    quote: str
    line: int = Field(ge=1)
    strength: float = Field(ge=0.0, le=1.0)
    source: str = "resume"


class MissingRequirement(BaseModel):
    requirement: str
    weight: int = Field(ge=1)
    must_have: bool = False
    why: str = ""


class NextBandAction(BaseModel):
    action: str
    target_requirement: str
    expected_gain: float = Field(ge=0.0)


class Rubric(BaseModel):
    semantic: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    raw_score: float = Field(ge=0.0, le=10.0)
    calibrated_score: float = Field(ge=0.0, le=10.0)
    semantic_weight: float = 0.6
    coverage_weight: float = 0.4
    calibration_version: str = "identity"


class PrivacyInfo(BaseModel):
    llm_enabled: bool
    consent_given: bool
    external_llm_used: bool
    retention_note: str


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    request_id: str
    score: float = Field(ge=0.0, le=10.0)
    band: ScoreBand
    matched_role: str
    alternative_roles: list[RoleMatch] = Field(default_factory=list)
    improvements: list[Improvement] = Field(default_factory=list)
    extracted_entities: ExtractedEntities
    rubric: Rubric
    evidence: list[EvidenceItem] = Field(default_factory=list)
    missing_requirements: list[MissingRequirement] = Field(default_factory=list)
    next_band_actions: list[NextBandAction] = Field(default_factory=list)
    scoring_source: ScoringSource
    llm_model: str | None = None
    embedding_model: str
    jd_used: bool = False
    privacy: PrivacyInfo


class HealthResponse(BaseModel):
    status: str
    version: str
    ready: bool = True
    embedding_model: str | None = None
    llm_configured: bool = False


class RoleResponse(BaseModel):
    roles: list[str]


class ConfigResponse(BaseModel):
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_fallback: str
    require_consent: bool
    max_upload_mb: int
    max_jd_chars: int
    sample_pdf_url: str = "/samples/sample-resume.pdf"
    sample_docx_url: str = "/samples/sample-resume.docx"
    privacy_url: str = "/privacy.html"
    version: str


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
