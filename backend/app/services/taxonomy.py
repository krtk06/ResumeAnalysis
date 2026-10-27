from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Skill:
    canonical: str
    family: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class SkillMatch:
    canonical: str
    family: str
    alias: str
    start: int
    end: int


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    weight: int = 1
    must_have: bool = False
    accepts: tuple[str, ...] = ()
    families: tuple[str, ...] = ()

    def satisfied_by(self, skill: Skill) -> bool:
        return skill.canonical in self.accepts or skill.family in self.families


@dataclass(frozen=True)
class Role:
    name: str
    description: str
    requirements: tuple[Requirement, ...]


def _alias_pattern(alias: str) -> re.Pattern[str]:
    # Word-ish boundaries, but allow symbols such as c++, c#, node.js.
    escaped = re.escape(alias.strip())
    return re.compile(
        rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )


class SkillTaxonomy:
    def __init__(self, skills: Iterable[Skill]):
        self.skills = tuple(skills)
        self.by_canonical = {skill.canonical: skill for skill in self.skills}
        self._patterns: list[tuple[re.Pattern[str], Skill]] = []
        for skill in self.skills:
            for alias in skill.aliases:
                if alias.strip():
                    self._patterns.append((_alias_pattern(alias), skill))
        # Longer aliases win when spans overlap: React Native > React, Node.js > Node.
        self._patterns.sort(key=lambda item: len(item[0].pattern), reverse=True)

    def match(self, text: str) -> list[SkillMatch]:
        if not text:
            return []

        raw: list[SkillMatch] = []
        for pattern, skill in self._patterns:
            for found in pattern.finditer(text):
                raw.append(
                    SkillMatch(
                        canonical=skill.canonical,
                        family=skill.family,
                        alias=found.group(0),
                        start=found.start(),
                        end=found.end(),
                    )
                )

        if not raw:
            return []

        raw.sort(key=lambda match: (match.start, -(match.end - match.start)))
        accepted: list[SkillMatch] = []
        occupied_until = -1
        for match in raw:
            if match.start >= occupied_until:
                accepted.append(match)
                occupied_until = match.end
        return accepted

    def grouped(self, text: str) -> dict[str, SkillMatch]:
        grouped: dict[str, SkillMatch] = {}
        for match in self.match(text):
            grouped.setdefault(match.canonical, match)
        return grouped

    def names(self, text: str) -> list[str]:
        return sorted(self.grouped(text).keys())


def load_skills(path: Path | None = None) -> SkillTaxonomy:
    data = yaml.safe_load((path or DATA_DIR / "skills.yaml").read_text(encoding="utf-8"))
    skills = []
    seen: set[str] = set()
    for item in data["skills"]:
        canonical = str(item["canonical"]).strip()
        if canonical in seen:
            raise ValueError(f"Duplicate canonical skill: {canonical}")
        seen.add(canonical)
        aliases = tuple(str(alias).strip().lower() for alias in item.get("aliases", []))
        skills.append(Skill(canonical=canonical, family=str(item["family"]), aliases=aliases))
    return SkillTaxonomy(skills)


def load_roles(taxonomy: SkillTaxonomy, path: Path | None = None) -> tuple[Role, ...]:
    data = yaml.safe_load((path or DATA_DIR / "roles.yaml").read_text(encoding="utf-8"))
    roles: list[Role] = []
    known = set(taxonomy.by_canonical)
    for item in data["roles"]:
        requirements = []
        for raw in item.get("requirements", []):
            accepts = tuple(str(name) for name in raw.get("accepts", []))
            unknown = [name for name in accepts if name not in known]
            if unknown:
                raise ValueError(f"Role {item['name']} references unknown skills: {unknown}")
            requirements.append(
                Requirement(
                    id=str(raw["id"]),
                    text=str(raw["text"]),
                    weight=int(raw.get("weight", 1)),
                    must_have=bool(raw.get("must_have", False)),
                    accepts=accepts,
                    families=tuple(str(name) for name in raw.get("families", [])),
                )
            )
        roles.append(
            Role(
                name=str(item["name"]),
                description=str(item["description"]).strip(),
                requirements=tuple(requirements),
            )
        )
    return tuple(roles)


@lru_cache(maxsize=1)
def get_taxonomy() -> SkillTaxonomy:
    return load_skills()


@lru_cache(maxsize=1)
def get_roles() -> tuple[Role, ...]:
    return load_roles(get_taxonomy())


def find_role(roles: Iterable[Role], target_role: str) -> Role | None:
    target = target_role.strip().lower()
    if not target:
        return None
    exact = [role for role in roles if role.name.lower() == target]
    if exact:
        return exact[0]
    contained = [role for role in roles if role.name.lower() in target]
    if contained:
        return max(contained, key=lambda role: len(role.name))
    reversed_match = [role for role in roles if target in role.name.lower()]
    if reversed_match:
        return max(reversed_match, key=lambda role: len(role.name))
    return None


_JD_IMPLICATIONS: dict[str, tuple[str, ...]] = {
    "Database Design": (
        "Database Design",
        "SQL",
        "PostgreSQL",
        "MySQL",
        "SQLite",
        "MongoDB",
        "Redis",
    ),
    "REST APIs": ("REST APIs", "FastAPI", "Django", "Flask", "Express", "Spring", "NestJS", "GraphQL"),
    "CI/CD": ("CI/CD", "GitHub Actions", "Jenkins", "GitLab CI"),
    "Observability": ("Observability", "Prometheus", "Grafana"),
    "Unit Testing": ("Unit Testing", "PyTest", "Jest"),
    "Test Automation": ("Test Automation", "Playwright", "Cypress", "Selenium"),
    "Data Visualization": ("Data Visualization", "Tableau", "Power BI", "Matplotlib", "Seaborn"),
    "Reporting": ("Reporting", "Tableau", "Power BI"),
    "MLOps": ("MLOps", "Docker", "Kubernetes", "AWS", "GCP", "Azure"),
    "Security Best Practices": (
        "Security Best Practices",
        "OWASP",
        "Authentication",
        "IAM",
        "Encryption",
    ),
}


_JD_ABSORB: dict[str, tuple[str, ...]] = {
    # A brief that says "observability with Prometheus or Grafana" is asking
    # for one capability, not three separate requirements. Collapse only when
    # the child is not weighted more heavily than the parent.
    "Observability": ("Prometheus", "Grafana"),
    "CI/CD": ("Jenkins", "GitHub Actions"),
}


def requirements_from_jd(
    jd_text: str,
    taxonomy: SkillTaxonomy,
    *,
    max_requirements: int = 20,
) -> tuple[Requirement, ...]:
    """Extract weighted requirements from a pasted job description.

    This is deliberately taxonomy-driven: it is deterministic, cheap, and
    explains every requirement. An LLM can be layered on later, but the local
    path must always work.
    """
    if not jd_text.strip():
        return ()

    grouped = taxonomy.grouped(jd_text)
    if not grouped:
        return ()

    lines = [line.strip().lower() for line in jd_text.splitlines() if line.strip()]
    weighted: dict[str, tuple[int, bool, str]] = {}

    for canonical in grouped:
        context = ""
        for line in lines:
            if any(alias.lower() in line for alias in taxonomy.by_canonical[canonical].aliases):
                context = line
                break
        must_have = any(token in context for token in ("must", "required", "minimum", "essential"))
        preferred = any(token in context for token in ("preferred", "nice to have", "bonus", "plus"))
        weight = 3 if must_have else 1 if preferred else 2
        weighted[canonical] = (weight, must_have, context)

    for parent, children in _JD_ABSORB.items():
        if parent not in weighted:
            continue
        parent_weight = weighted[parent][0]
        for child in children:
            if child in weighted and weighted[child][0] <= parent_weight:
                weighted.pop(child, None)

    ordered = sorted(weighted.items(), key=lambda item: (item[1][0], item[0]), reverse=True)
    requirements = []
    for index, (canonical, (weight, must_have, _context)) in enumerate(ordered[:max_requirements], start=1):
        requirements.append(
            Requirement(
                id=f"jd-{index}-{canonical.lower().replace(' ', '-')}",
                text=canonical,
                weight=weight,
                must_have=must_have,
                accepts=_JD_IMPLICATIONS.get(canonical, (canonical,)),
            )
        )
    return tuple(requirements)
