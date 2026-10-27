from __future__ import annotations

import re
from dataclasses import dataclass, field

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"\bhttps?://[^\s<>()]+", re.IGNORECASE)
_HANDLE_RE = re.compile(r"\b(?:linkedin\.com|github\.com)/[A-Za-z0-9_./-]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}(?!\d)")
_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9.'-]*(?:\s+[A-Z][A-Za-z0-9.'-]*){0,3}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b\.?",
    re.IGNORECASE,
)
_NAME_LINE_RE = re.compile(r"^(?:name\s*[:\-]\s*)?([A-Z][a-zA-Z'.-]+(?:\s+[A-Z][a-zA-Z'.-]+){1,3})$")


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)


def _replace(pattern: re.Pattern[str], replacement: str, text: str, counts: dict[str, int]) -> str:
    text, count = pattern.subn(replacement, text)
    if count:
        counts[replacement.strip("[]").lower()] = count
    return text


def redact_pii(text: str) -> RedactionResult:
    """Redact high-confidence PII before sending text to an external LLM.

    This is defence in depth, not a guarantee. Names are the hardest case; the
    heuristic only rewrites a name-like line near the top of the document.
    """
    counts: dict[str, int] = {}
    redacted = text.replace("\r\n", "\n").replace("\r", "\n")
    redacted = _replace(_EMAIL_RE, "[EMAIL]", redacted, counts)
    redacted = _replace(_HANDLE_RE, "[PROFILE]", redacted, counts)
    redacted = _replace(_URL_RE, "[URL]", redacted, counts)
    redacted = _replace(_PHONE_RE, "[PHONE]", redacted, counts)
    redacted = _replace(_ADDRESS_RE, "[ADDRESS]", redacted, counts)

    lines = redacted.splitlines()
    replaced_names = 0
    for index, line in enumerate(lines[:6]):
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue
        if re.search(
            r"\d|@|http|linkedin|github|resume|curriculum|experience|education", stripped, re.IGNORECASE
        ):
            continue
        if _NAME_LINE_RE.match(stripped):
            lines[index] = "[NAME]"
            replaced_names += 1
            break
    if replaced_names:
        counts["name"] = replaced_names

    return RedactionResult(text="\n".join(lines), counts=counts)
