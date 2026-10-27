from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from .taxonomy import SkillMatch, SkillTaxonomy, get_taxonomy

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE_RANGE_RE = re.compile(
    rf"(?:(?P<m1>{_MONTH_PATTERN})[\s,./-]*)?(?P<y1>(?:19|20)\d{{2}})"
    rf"\s*(?:-|–|—|to|through)\s*"
    rf"(?:(?P<m2>{_MONTH_PATTERN})[\s,./-]*)?(?P<y2>(?:19|20)\d{{2}}|present|current|now|today)",
    re.IGNORECASE,
)
_EXPLICIT_YEARS_RE = re.compile(
    r"(?P<years>\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?(?:experience|exp)\b",
    re.IGNORECASE,
)
_DEGREE_RE = re.compile(
    r"\b(?:bachelor(?:'s)?|master(?:'s)?|ph\.?\s?d|doctorate|b\.?\s?tech|m\.?\s?tech|b\.?\s?sc|m\.?\s?sc|b\.?\s?e|m\.?\s?e|b\.?\s?a|m\.?\s?a|mba|bcom|mcom)\b",
    re.IGNORECASE,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:university|college|institute|school|academy|iit|nit|iiit|bits)\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}")
_SECTION_HEADINGS = {
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
        "career history",
    ),
    "education": ("education", "academic background", "academics", "qualifications"),
    "skills": ("skills", "technical skills", "core competencies", "technologies"),
    "projects": ("projects", "selected projects", "personal projects"),
    "certifications": ("certifications", "certificates", "licenses"),
}


@dataclass
class NLPResult:
    skills: list[str]
    skill_details: list[dict[str, str | int]]
    education: list[str]
    experience_years: float
    experience_months: int
    resume_confidence: float
    signals: list[str]
    skill_matches: list[SkillMatch] = field(default_factory=list)


def _month_number(name: str | None) -> int | None:
    if not name:
        return None
    return MONTHS.get(name[:3].lower())


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _range_to_interval(match: re.Match[str], today: date) -> tuple[int, int] | None:
    start_year = int(match.group("y1"))
    end_raw = match.group("y2").lower()
    end_year = today.year if end_raw in {"present", "current", "now", "today"} else int(end_raw)
    start_month = _month_number(match.group("m1")) or 1
    if end_raw in {"present", "current", "now", "today"}:
        end_month = today.month
    else:
        end_month = _month_number(match.group("m2")) or 12

    start = _month_index(start_year, start_month)
    end = _month_index(end_year, end_month) + 1  # inclusive month
    if end <= start:
        return None
    if end - start > 12 * 60:  # ignore implausible 60+ year spans
        return None
    return start, end


def _union_months(intervals: Iterable[tuple[int, int]]) -> int:
    ordered = sorted(intervals)
    if not ordered:
        return 0
    total = 0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    total += current_end - current_start
    return max(total, 0)


def _heading_key(line: str) -> str | None:
    cleaned = re.sub(r"[^a-z ]", " ", line.lower()).strip()
    if not cleaned or len(cleaned.split()) > 5:
        return None
    for key, names in _SECTION_HEADINGS.items():
        if any(cleaned == name or cleaned.startswith(name) for name in names):
            return key
    return None


def _section(lines: tuple[str, ...], key: str) -> tuple[str, ...]:
    start = None
    for index, line in enumerate(lines):
        if _heading_key(line) == key:
            start = index + 1
            break
    if start is None:
        return ()
    end = len(lines)
    for index in range(start, len(lines)):
        heading = _heading_key(lines[index])
        if heading and heading != key:
            end = index
            break
    return lines[start:end]


def _experience_text(lines: tuple[str, ...]) -> str:
    section = _section(lines, "experience")
    if section:
        return "\n".join(section)
    education = set(_section(lines, "education"))
    return "\n".join(line for line in lines if line not in education)


def extract_experience_months(text: str, lines: tuple[str, ...], today: date | None = None) -> int:
    today = today or date.today()
    experience_text = _experience_text(lines) or text
    intervals = []
    for match in _DATE_RANGE_RE.finditer(experience_text):
        interval = _range_to_interval(match, today)
        if interval:
            intervals.append(interval)
    dated_months = _union_months(intervals)

    explicit = [
        float(match.group("years"))
        for match in _EXPLICIT_YEARS_RE.finditer(text)
        if 0 < float(match.group("years")) <= 50
    ]
    explicit_months = int(max(explicit, default=0) * 12)
    return min(max(dated_months, explicit_months), 12 * 50)


def extract_education(text: str, lines: tuple[str, ...]) -> list[str]:
    source = _section(lines, "education") or lines
    if not source:
        return []

    degrees: list[str] = []
    institutions: list[str] = []
    for line in source:
        compact = re.sub(r"\s+", " ", line).strip(" |-–—")
        if not compact or len(compact) < 4:
            continue
        if _DEGREE_RE.search(compact):
            degrees.append(compact[:180])
        elif _INSTITUTION_RE.search(compact):
            institutions.append(compact[:180])

    combined: list[str] = []
    for degree in degrees:
        match = next(
            (inst for inst in institutions if inst not in degree and len(inst) > 3),
            None,
        )
        combined.append(f"{degree} — {match}" if match else degree)

    if not combined:
        combined.extend(institutions)

    deduped: list[str] = []
    for item in combined:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _resume_signals(
    text: str,
    lines: tuple[str, ...],
    skills: list[str],
    education: list[str],
    experience_months: int,
) -> tuple[float, list[str]]:
    signals: list[str] = []
    score = 0.0

    if _EMAIL_RE.search(text) or _PHONE_RE.search(text) or re.search(r"linkedin|github", text, re.IGNORECASE):
        score += 0.25
        signals.append("contact details present")
    if experience_months > 0 or _section(lines, "experience"):
        score += 0.20
        signals.append("experience section or dated roles")
    if education:
        score += 0.15
        signals.append("education evidence")
    if len(skills) >= 3:
        score += 0.15
        signals.append("multiple skills")
    if _section(lines, "skills"):
        score += 0.05
        signals.append("skills section")

    first_lines = [line for line in lines[:5] if line]
    if any(
        2 <= len(line.split()) <= 4
        and not re.search(r"\d|@|http|resume|curriculum", line, re.IGNORECASE)
        and sum(word[:1].isupper() for word in line.split()) >= 2
        for line in first_lines
    ):
        score += 0.10
        signals.append("name-like header")

    if sum(1 for line in lines if line.lstrip().startswith(("-", "•", "*"))) >= 3:
        score += 0.05
        signals.append("bullet points")

    negative_terms = (
        "scope of work",
        "deliverables",
        "statement of work",
        "table of contents",
        "abstract",
        "methodology",
        "references",
        "bibliography",
        "license agreement",
        "terms and conditions",
    )
    lowered = text.lower()
    negatives = [term for term in negative_terms if term in lowered]
    if negatives:
        score -= 0.25
        signals.append(f"non-resume language: {negatives[0]}")
    if len(text) < 300:
        score -= 0.30
        signals.append("very short document")
    if len(skills) <= 1:
        score -= 0.10
        signals.append("few recognizable skills")

    return max(0.0, min(1.0, score)), signals


class NLPAnalyzer:
    def __init__(self, taxonomy: SkillTaxonomy | None = None):
        self.taxonomy = taxonomy or get_taxonomy()

    def extract_skills(self, text: str) -> list[str]:
        return self.taxonomy.names(text)

    def analyze(
        self, text: str, lines: tuple[str, ...] | None = None, today: date | None = None
    ) -> NLPResult:
        source_lines = lines or tuple(line for line in text.splitlines() if line.strip())
        matches = self.taxonomy.match(text)
        counts: dict[str, tuple[str, int]] = {}
        for match in matches:
            family, count = counts.get(match.canonical, (match.family, 0))
            counts[match.canonical] = (family, count + 1)

        skill_details: list[dict[str, str | int]] = [
            {"name": name, "family": family, "mentions": count}
            for name, (family, count) in sorted(counts.items(), key=lambda item: (-item[1][1], item[0]))
        ]
        skills = [str(item["name"]) for item in skill_details]
        education = extract_education(text, source_lines)
        months = extract_experience_months(text, source_lines, today=today)
        confidence, signals = _resume_signals(text, source_lines, skills, education, months)

        return NLPResult(
            skills=skills,
            skill_details=skill_details,
            education=education,
            experience_years=round(months / 12, 1),
            experience_months=months,
            resume_confidence=confidence,
            signals=signals,
            skill_matches=matches,
        )
