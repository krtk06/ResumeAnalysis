from datetime import date

from app.services.nlp_analyzer import (
    NLPAnalyzer,
    extract_education,
    extract_experience_months,
)
from app.services.taxonomy import get_taxonomy


def _nlp() -> NLPAnalyzer:
    return NLPAnalyzer(get_taxonomy())


def test_skills_are_canonical_and_deduplicated():
    result = _nlp().analyze("Python, Python, JavaScript, React and PostgreSQL.", today=date(2026, 10, 1))
    assert set(result.skills) == {"Python", "JavaScript", "PostgreSQL", "React"}
    assert next(item for item in result.skill_details if item["name"] == "Python")["mentions"] == 2


def test_experience_uses_current_year_and_unions_overlaps():
    lines = (
        "EXPERIENCE",
        "Engineer, A, Jan 2020 - Present",
        "Senior Engineer, B, Jan 2022 - Dec 2023",
        "EDUCATION",
        "B.Tech, Example University, 2015 - 2019",
    )
    months = extract_experience_months("\n".join(lines), lines, today=date(2026, 10, 1))
    # Jan 2020 through Oct 2026 inclusive is 82 months; the overlapping role
    # must not add another 24 months.
    assert months == 82


def test_explicit_years_fallback():
    lines = ("EXPERIENCE", "Five years of hands-on work.")
    assert extract_experience_months("5+ years of experience", lines, today=date(2026, 10, 1)) == 60


def test_education_section():
    lines = (
        "EDUCATION",
        "B.Tech in Computer Science, IIT Delhi",
        "SKILLS",
        "Python",
    )
    education = extract_education("\n".join(lines), lines)
    assert any("B.Tech" in item for item in education)


def test_non_resume_confidence_is_low():
    result = _nlp().analyze(
        "Scope of Work\nDeliverables\nThis document describes milestones and payment terms.",
        today=date(2026, 10, 1),
    )
    assert result.resume_confidence < 0.3
    assert "non-resume language" in " ".join(result.signals)


def test_resume_confidence_is_high(resume_text, today):
    result = _nlp().analyze(resume_text, today=today)
    assert result.resume_confidence >= 0.6
    assert result.experience_months > 0
    assert "Python" in result.skills
