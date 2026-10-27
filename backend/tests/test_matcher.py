from app.ml import HashingEmbedder
from app.services.matcher import Calibrator, RoleMatcher
from app.services.nlp_analyzer import NLPAnalyzer
from app.services.taxonomy import get_roles, get_taxonomy


def _matcher(calibrator=None):
    taxonomy = get_taxonomy()
    return RoleMatcher(taxonomy, get_roles(), HashingEmbedder(), calibrator), taxonomy


def test_calibrator_interpolates():
    calibrator = Calibrator([[0, 0], [5, 6], [10, 10]], "test")
    assert calibrator.calibrate(5) == 6.0
    assert calibrator.calibrate(-2) == 0.0
    assert calibrator.calibrate(20) == 10.0


def test_match_returns_rubric_and_evidence(resume_text, resume_lines, today):
    matcher, taxonomy = _matcher()
    nlp = NLPAnalyzer(taxonomy).analyze(resume_text, resume_lines, today=today)
    result = matcher.match(resume_text, resume_lines, nlp, "Software Engineer")

    assert result.matched_role == "Software Engineer"
    assert 0 <= result.score <= 10
    assert result.rubric.calibration_version == "identity"
    expected_raw = round(10 * (0.6 * result.rubric.semantic + 0.4 * result.rubric.coverage), 1)
    assert result.rubric.raw_score == expected_raw
    assert result.rubric.calibrated_score == result.score
    assert result.evidence
    assert all(item.line >= 1 for item in result.evidence)
    assert result.missing_requirements is not None
    assert result.next_band_actions


def test_jd_uses_jd_requirements(resume_text, resume_lines, jd_text, today):
    matcher, taxonomy = _matcher()
    nlp = NLPAnalyzer(taxonomy).analyze(resume_text, resume_lines, today=today)
    result = matcher.match(resume_text, resume_lines, nlp, "Software Engineer", jd_text)
    assert result.jd_used is True
    seen = {item.requirement for item in result.missing_requirements}
    seen.update(item.requirement for item in result.evidence)
    assert seen & {"Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "REST APIs", "Kubernetes"}


def test_alternative_roles_are_returned(resume_text, resume_lines, today):
    matcher, taxonomy = _matcher()
    nlp = NLPAnalyzer(taxonomy).analyze(resume_text, resume_lines, today=today)
    result = matcher.match(resume_text, resume_lines, nlp, "Software Engineer")
    assert result.alternative_roles
    assert all(0 <= item.match <= 1 for item in result.alternative_roles)


def test_missing_requirements_are_ranked(resume_text, resume_lines, today):
    matcher, taxonomy = _matcher()
    nlp = NLPAnalyzer(taxonomy).analyze(
        "Python only. No other skills.", ("Python only. No other skills.",), today=today
    )
    result = matcher.match(
        "Python only. No other skills.", ("Python only. No other skills.",), nlp, "Software Engineer"
    )
    assert result.missing_requirements
    assert result.missing_requirements[0].must_have is True
