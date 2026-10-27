from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..ml import Embedder, cosine_similarity
from ..models.schemas import (
    EvidenceItem,
    Improvement,
    MissingRequirement,
    NextBandAction,
    Priority,
    RoleMatch,
    Rubric,
    ScoreBand,
)
from .nlp_analyzer import NLPResult
from .redaction import redact_pii
from .taxonomy import (
    Requirement,
    Role,
    Skill,
    SkillTaxonomy,
    find_role,
    requirements_from_jd,
)

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    score: float
    band: ScoreBand
    matched_role: str
    alternative_roles: list[RoleMatch]
    improvements: list[Improvement]
    rubric: Rubric
    evidence: list[EvidenceItem]
    missing_requirements: list[MissingRequirement]
    next_band_actions: list[NextBandAction]
    jd_used: bool
    role_description: str


class Calibrator:
    def __init__(self, points: Sequence[Sequence[float]] | None = None, version: str = "identity"):
        self.points = sorted((float(x), float(y)) for x, y in points or [])
        self.version = version

    @classmethod
    def from_path(cls, path: str | None) -> Calibrator:
        if not path:
            return cls()
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            points = data.get("points", [])
            version = str(data.get("version", "custom"))
            if len(points) < 2:
                return cls()
            return cls(points, version)
        except Exception as exc:
            logger.warning("Could not load calibration file %s: %s", path, exc)
            return cls()

    def calibrate(self, value: float) -> float:
        value = max(0.0, min(10.0, value))
        if not self.points:
            return round(value, 1)
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        calibrated = float(np.interp(value, xs, ys))
        return round(max(0.0, min(10.0, calibrated)), 1)


def _band(score: float) -> ScoreBand:
    if score >= 8:
        return ScoreBand.EXCELLENT
    if score >= 6:
        return ScoreBand.GOOD
    if score >= 4:
        return ScoreBand.MODERATE
    return ScoreBand.NEEDS_WORK


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class RoleMatcher:
    def __init__(
        self,
        taxonomy: SkillTaxonomy,
        roles: Sequence[Role],
        embedder: Embedder,
        calibrator: Calibrator | None = None,
    ):
        self.taxonomy = taxonomy
        self.roles = tuple(roles)
        self.embedder = embedder
        self.calibrator = calibrator or Calibrator()
        self.role_embeddings: dict[str, np.ndarray] = {}
        self._target_cache: dict[str, np.ndarray] = {}
        self._embed_roles()

    def _embed_roles(self) -> None:
        try:
            descriptions = [role.description for role in self.roles]
            vectors = self.embedder.encode(descriptions)
            for role, vector in zip(self.roles, vectors, strict=False):
                self.role_embeddings[role.name] = vector
        except Exception as exc:
            logger.exception("Could not embed role descriptions: %s", exc)

    def _target_embedding(self, text: str) -> np.ndarray | None:
        key = text[:500]
        if key in self._target_cache:
            return self._target_cache[key]
        try:
            vector = self.embedder.encode([text])[0]
        except Exception as exc:
            logger.exception("Target embedding failed: %s", exc)
            return None
        if len(self._target_cache) > 32:
            self._target_cache.clear()
        self._target_cache[key] = vector
        return vector

    @staticmethod
    def _chunks(text: str, chunk_chars: int = 900, overlap: int = 150) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_chars:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + chunk_chars])
            if start + chunk_chars >= len(text):
                break
            start += chunk_chars - overlap
        return chunks

    def _semantic_score(self, resume_text: str, target_text: str) -> float:
        chunks = self._chunks(resume_text)
        target = self._target_embedding(target_text)
        if not chunks or target is None:
            return 0.0
        try:
            chunk_vectors = self.embedder.encode(chunks)
            sims = cosine_similarity(chunk_vectors, target)
        except Exception as exc:
            logger.exception("Semantic scoring failed: %s", exc)
            return 0.0
        if len(sims) == 0:
            return 0.0
        best = float(np.max(sims))
        top = np.sort(sims)[-3:]
        top_mean = float(np.mean(top))
        return _clamp(0.6 * best + 0.4 * top_mean)

    def _select_requirements(
        self, target_role: str, jd_text: str | None
    ) -> tuple[Role | None, tuple[Requirement, ...], str, bool]:
        role = find_role(self.roles, target_role)
        jd_requirements = requirements_from_jd(jd_text, self.taxonomy) if jd_text else ()
        if jd_requirements:
            requirements = list(jd_requirements)
            if role and len(requirements) < 3:
                existing = {item.text for item in requirements}
                for item in role.requirements:
                    if item.text not in existing:
                        requirements.append(item)
            target_text = (jd_text or "") + "\n" + (role.description if role else target_role)
            return role, tuple(requirements), target_text, True
        if role:
            return role, role.requirements, role.description, False
        return None, (), target_role, False

    def _coverage(
        self, requirements: Sequence[Requirement], matched: dict[str, Skill]
    ) -> tuple[float, list[Requirement], list[Requirement]]:
        if not requirements:
            return 0.5, [], []
        total_weight = sum(item.weight for item in requirements) or 1
        matched_weight = 0
        matched_requirements: list[Requirement] = []
        missing: list[Requirement] = []
        for requirement in requirements:
            if any(requirement.satisfied_by(skill) for skill in matched.values()):
                matched_weight += requirement.weight
                matched_requirements.append(requirement)
            else:
                missing.append(requirement)
        return matched_weight / total_weight, matched_requirements, missing

    def _line_evidence(
        self,
        lines: Sequence[str],
        requirements: Sequence[Requirement],
        matched: dict[str, Skill],
    ) -> list[EvidenceItem]:
        if not lines:
            return []

        line_matches = [self.taxonomy.match(line) for line in lines]
        verb_re = re.compile(
            r"\b(?:built|designed|led|shipped|developed|created|improved|reduced|"
            r"automated|deployed|managed|launched|implemented|owned|migrated)\b",
            re.IGNORECASE,
        )

        def is_list_line(line: str) -> bool:
            return (line.count(",") >= 3 or line.count("|") >= 2) and not verb_re.search(line)

        def is_bare_skill_requirement(requirement: Requirement) -> bool:
            if len(requirement.accepts) != 1:
                return False
            return requirement.text.strip().lower() == requirement.accepts[0].strip().lower()

        def candidate_score(index: int, requirement: Requirement) -> float:
            matches = line_matches[index]
            requirement_hits = sum(
                1
                for match in matches
                if requirement.satisfied_by(self.taxonomy.by_canonical[match.canonical])
            )
            if requirement_hits == 0:
                return -1.0
            line = lines[index]
            if is_list_line(line) and not is_bare_skill_requirement(requirement):
                return -1.0
            length_score = min(len(line) / 140, 1.0)
            verb_bonus = 1.5 if verb_re.search(line) else 0.0
            list_penalty = 2.0 if is_list_line(line) else 0.0
            return 4.0 * requirement_hits + verb_bonus + length_score - list_penalty

        evidence: list[EvidenceItem] = []
        for requirement in requirements:
            if not any(requirement.satisfied_by(skill) for skill in matched.values()):
                continue
            scored = [
                (candidate_score(index, requirement), index)
                for index in range(len(lines))
                if candidate_score(index, requirement) >= 0
            ]
            # Prefer a real bullet/role line over a bare skills list. If the
            # requirement is just a skill name, a skills-list citation is an
            # acceptable last resort.
            non_list = [(score, index) for score, index in scored if not is_list_line(lines[index])]
            hit_line = max(non_list)[1] if non_list else (max(scored)[1] if scored else None)

            if hit_line is not None:
                evidence.append(
                    EvidenceItem(
                        requirement=requirement.text,
                        quote=lines[hit_line][:300],
                        line=hit_line + 1,
                        strength=1.0,
                    )
                )
                continue

            # Fall back to semantic line retrieval for paraphrased evidence.
            try:
                sample = list(lines[:100])
                line_vectors = self.embedder.encode(sample)
                requirement_vector = self.embedder.encode([requirement.text])[0]
                sims = cosine_similarity(line_vectors, requirement_vector)
                ranked = np.argsort(sims)[::-1][:6]
                best_index = -1
                best_rank = -1.0
                for index in ranked:
                    line = sample[int(index)]
                    if is_list_line(line) and not is_bare_skill_requirement(requirement):
                        continue
                    penalty = 0.25 if is_list_line(line) else 0.0
                    rank = float(sims[int(index)]) - penalty
                    if rank > best_rank and rank >= 0.35:
                        best_rank = rank
                        best_index = int(index)
                if best_index >= 0:
                    evidence.append(
                        EvidenceItem(
                            requirement=requirement.text,
                            quote=sample[best_index][:300],
                            line=best_index + 1,
                            strength=round(max(0.0, best_rank), 2),
                        )
                    )
            except Exception as exc:
                logger.warning("Semantic evidence lookup failed: %s", exc)
        return evidence

    def _alternative_roles(self, resume_text: str, matched_role: str) -> list[RoleMatch]:
        if not self.role_embeddings:
            return []
        chunks = self._chunks(resume_text)
        if not chunks:
            return []
        try:
            chunk_vectors = self.embedder.encode(chunks)
        except Exception as exc:
            logger.warning("Alternative role scoring failed: %s", exc)
            return []

        scored: list[tuple[str, float]] = []
        for role, vector in self.role_embeddings.items():
            if role == matched_role:
                continue
            sims = cosine_similarity(chunk_vectors, vector)
            if len(sims):
                scored.append((role, float(np.max(sims))))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            RoleMatch(role=role, match=round(_clamp(score), 2)) for role, score in scored[:3] if score >= 0.20
        ]

    def _improvements(self, missing: Sequence[Requirement], score: float) -> list[Improvement]:
        ordered = sorted(missing, key=lambda item: (item.must_have, item.weight), reverse=True)
        improvements: list[Improvement] = []
        for requirement in ordered[:4]:
            improvements.append(
                Improvement(
                    area=requirement.text,
                    priority=Priority.HIGH if requirement.must_have else Priority.MEDIUM,
                    action=(
                        "Add a specific project or role bullet that demonstrates "
                        f"{requirement.text.lower()}, with scope and a measurable result."
                    ),
                )
            )
        if not improvements:
            improvements = [
                Improvement(
                    area="Quantify the strongest achievements",
                    priority=Priority.MEDIUM,
                    action="Add numbers (users, revenue, latency, scale) to the most relevant bullets.",
                ),
                Improvement(
                    area="Lead with role-relevant evidence",
                    priority=Priority.MEDIUM,
                    action="Move the most relevant project or impact above older, less relevant experience.",
                ),
            ]
        if score >= 8:
            improvements.insert(
                0,
                Improvement(
                    area="Strong match — make the evidence impossible to miss",
                    priority=Priority.HIGH,
                    action="Put the two strongest role-relevant outcomes in the top third of page one.",
                ),
            )
        return improvements[:4]

    def _next_band_actions(
        self,
        missing: Sequence[Requirement],
        score: float,
        requirements: Sequence[Requirement],
    ) -> list[NextBandAction]:
        total_weight = sum(item.weight for item in requirements) or 1
        gap = max(0.0, 8.0 - score)
        ordered = sorted(missing, key=lambda item: (item.must_have, item.weight), reverse=True)
        actions: list[NextBandAction] = []
        for requirement in ordered[:3]:
            potential = min(gap, 10 * 0.4 * (requirement.weight / total_weight))
            actions.append(
                NextBandAction(
                    action=(
                        f"Show {requirement.text.lower()} in a real outcome: what you built, "
                        "the scale, and the measurable result."
                    ),
                    target_requirement=requirement.text,
                    expected_gain=round(max(0.0, potential), 1),
                )
            )
        if not actions and score < 8:
            actions.append(
                NextBandAction(
                    action="Quantify the impact of your two strongest bullets and move them above the fold.",
                    target_requirement="Impact evidence",
                    expected_gain=round(min(gap, 0.5), 1),
                )
            )
        return actions

    def match(
        self,
        resume_text: str,
        lines: Sequence[str],
        nlp: NLPResult,
        target_role: str,
        jd_text: str | None = None,
    ) -> MatchResult:
        role, requirements, target_text, jd_used = self._select_requirements(target_role, jd_text)
        matched_skills = {
            name: self.taxonomy.by_canonical[name]
            for name in nlp.skills
            if name in self.taxonomy.by_canonical
        }
        coverage, _matched_requirements, missing = self._coverage(requirements, matched_skills)
        # Names, email addresses, and phone numbers should not influence the
        # semantic score. The redacted copy is also what the optional LLM sees.
        semantic_text = redact_pii(resume_text).text or resume_text
        semantic = self._semantic_score(semantic_text, target_text)

        if requirements:
            raw_score = 10 * (0.6 * semantic + 0.4 * coverage)
        else:
            # A custom role without a JD has no explicit requirements. Do not
            # pretend that a zero coverage score is meaningful.
            raw_score = 10 * (0.75 * semantic + 0.25 * 0.5)

        raw_score = round(max(0.0, min(10.0, raw_score)), 1)
        calibrated = self.calibrator.calibrate(raw_score)
        matched_role = role.name if role else target_role.strip()

        evidence = self._line_evidence(lines, requirements, matched_skills)
        alternatives = self._alternative_roles(semantic_text, matched_role)
        improvements = self._improvements(missing, calibrated)
        next_actions = self._next_band_actions(missing, calibrated, requirements)

        return MatchResult(
            score=calibrated,
            band=_band(calibrated),
            matched_role=matched_role,
            alternative_roles=alternatives,
            improvements=improvements,
            rubric=Rubric(
                semantic=round(semantic, 3),
                coverage=round(coverage, 3),
                raw_score=raw_score,
                calibrated_score=calibrated,
                calibration_version=self.calibrator.version,
            ),
            evidence=evidence,
            missing_requirements=[
                MissingRequirement(
                    requirement=requirement.text,
                    weight=requirement.weight,
                    must_have=requirement.must_have,
                    why=(
                        "Listed as a must-have requirement"
                        if requirement.must_have
                        else "Relevant requirement not found in the resume"
                    ),
                )
                for requirement in sorted(
                    missing, key=lambda item: (item.must_have, item.weight), reverse=True
                )
            ],
            next_band_actions=next_actions,
            jd_used=jd_used,
            role_description=role.description if role else target_role,
        )
