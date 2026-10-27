from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.llm_scorer import (
    LLMScorePayload,
    LLMScorer,
    _parse_json,
)
from app.services.rate_limit import LLMBudget, SlidingWindowLimiter
from app.services.redaction import redact_pii


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "environment": "test",
        "embedder_backend": "hash",
        "llm_enabled": True,
        "opencode_api_key": "test-key",
        "opencode_model": "beam-free",
        "opencode_fallback_model": "glm-5.3-flash",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(**values)


def test_parse_json_handles_code_fences():
    assert _parse_json('```json\n{"score": 5}\n```') == {"score": 5}
    assert _parse_json('text before {"score": 6} text after') == {"score": 6}


def test_bool_coercion_and_score_is_clamped_by_scorer():
    payload = LLMScorePayload(is_resume="false", score=12)
    assert payload.is_resume is False
    assert payload.score == 12


def test_redaction_removes_high_confidence_pii():
    result = redact_pii(
        "Alex Rivera\n"
        "alex@example.com | +1 555 123 4567 | https://example.com/alex\n"
        "12 Main Street, Springfield\n"
    )
    assert "[NAME]" in result.text
    assert "[EMAIL]" in result.text
    assert "[URL]" in result.text
    assert "[PHONE]" in result.text
    assert "[ADDRESS]" in result.text
    assert result.counts


def test_fabricated_evidence_is_dropped():
    scorer = LLMScorer(_settings(llm_enabled=False))
    lines = ("Alex Rivera", "Built REST APIs with Python and FastAPI.", "Education")
    payload = LLMScorePayload(
        score=7,
        evidence=[
            {"requirement": "REST APIs", "quote": "Built REST APIs with Python and FastAPI.", "line": 2},
            {"requirement": "Kubernetes", "quote": "Operated a 500-node Kubernetes cluster.", "line": 3},
        ],
    )
    evidence = scorer._verified_evidence(payload, lines, "\n".join(lines))
    assert len(evidence) == 1
    assert evidence[0].line == 2
    assert evidence[0].source == "llm_verified"


class FakeResponse:
    def __init__(self, payload: dict):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        self._payload = payload

    def model_dump(self):
        return {
            "usage": {
                "cost": 0.0,
                "opencode": {"billing_source": "go", "allowance": 0.01},
            }
        }


class FakeCompletions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["model"] == "beam-free":
            raise RuntimeError("403 model unavailable")
        return FakeResponse(
            {
                "is_resume": True,
                "score": 7.5,
                "label": "Good match",
                "reasoning": "Strong role alignment.",
                "missing": ["Kubernetes"],
                "evidence": [
                    {
                        "requirement": "REST APIs",
                        "quote": "Built REST APIs with Python and FastAPI.",
                        "line": 2,
                    }
                ],
                "alternative_roles": [{"role": "Backend Developer", "match": 0.7}],
            }
        )


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_llm_falls_back_to_glm_and_verifies_evidence():
    scorer = LLMScorer(_settings())
    fake = FakeClient()
    scorer._client = fake
    lines = ("Alex Rivera", "Built REST APIs with Python and FastAPI.", "Education")
    outcome = await scorer.score(
        resume_text="\n".join(lines),
        lines=lines,
        target_role="Software Engineer",
        role_description="Builds APIs.",
        skills=["Python", "FastAPI"],
    )
    assert outcome is not None
    assert outcome.model == "glm-5.3-flash"
    assert outcome.score == 7.5
    assert outcome.evidence[0].line == 2
    assert outcome.allowance_usd == 0.01
    assert fake.chat.completions.calls
    assert all("x-opencode-session" in call["extra_headers"] for call in fake.chat.completions.calls)


class BrokenCompletions:
    async def create(self, **kwargs):
        raise RuntimeError("invalid JSON")


class BrokenClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=BrokenCompletions())

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_llm_failure_returns_none():
    scorer = LLMScorer(_settings())
    scorer._client = BrokenClient()
    outcome = await scorer.score(
        resume_text="Alex Rivera\nPython",
        lines=("Alex Rivera", "Python"),
        target_role="Software Engineer",
        role_description="Builds APIs.",
        skills=["Python"],
    )
    assert outcome is None


def test_rate_limiter_windows():
    limiter = SlidingWindowLimiter(per_hour=2, per_day=3)
    assert limiter.check("ip", now=1000)[0] is True
    assert limiter.check("ip", now=1001)[0] is True
    allowed, retry = limiter.check("ip", now=1002)
    assert allowed is False
    assert retry > 0
    assert limiter.check("other", now=1002)[0] is True


def test_llm_budget_guard():
    budget = LLMBudget(max_requests_per_day=1, monthly_allowance_usd=10)
    assert budget.check()[0] is True
    budget.record(8.0)
    assert budget.check()[0] is False
