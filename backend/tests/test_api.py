from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _analyze(
    client: TestClient,
    data: bytes,
    filename: str = "resume.docx",
    *,
    jd: str | None = None,
    consent: bool = False,
):
    form = {"target_role": "Software Engineer"}
    if jd is not None:
        form["job_description"] = jd
    form["consent"] = "true" if consent else "false"
    return client.post(
        "/api/analyze",
        files={"file": (filename, data, DOCX if filename.endswith(".docx") else "application/pdf")},
        data=form,
    )


def test_health_ready_config_and_roles(client):
    assert client.get("/api/health").status_code == 200
    ready = client.get("/api/health/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    config = client.get("/api/config").json()
    assert config["llm_enabled"] is False
    assert config["max_upload_mb"] == 10
    assert len(client.get("/api/roles").json()["roles"]) == 10


def test_analyze_docx(client, docx_bytes):
    response = _analyze(client, docx_bytes)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["request_id"]
    assert response.headers["x-request-id"] == payload["request_id"]
    assert 0 <= payload["score"] <= 10
    assert payload["scoring_source"] == "local_llm_disabled"
    assert payload["extracted_entities"]["experience_months"] > 0
    assert "Python" in payload["extracted_entities"]["skills"]
    assert payload["rubric"]["calibration_version"] == "identity"
    assert payload["privacy"]["external_llm_used"] is False


def test_analyze_pdf(client, pdf_bytes):
    response = _analyze(client, pdf_bytes, "resume.pdf")
    assert response.status_code == 200, response.text
    assert response.json()["extracted_entities"]["skills"]


def test_analyze_with_jd(client, docx_bytes, jd_text):
    response = _analyze(client, docx_bytes, jd=jd_text)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jd_used"] is True
    assert payload["missing_requirements"]
    assert payload["evidence"]


def test_legacy_doc_rejected(client, docx_bytes):
    response = _analyze(client, docx_bytes, "resume.doc")
    assert response.status_code == 415
    assert ".docx" in response.json()["detail"]


def test_oversized_file_rejected(client):
    response = _analyze(client, b"x" * (10 * 1024 * 1024 + 1), "resume.pdf")
    assert response.status_code == 413


def test_non_resume_rejected(client):
    text = "Scope of Work\nDeliverables\nMilestones and payment terms."
    response = _analyze(client, text.encode(), "brief.pdf")
    assert response.status_code == 415


def test_non_resume_text_rejected(client, blank_pdf_bytes):
    response = _analyze(client, blank_pdf_bytes, "blank.pdf")
    assert response.status_code == 422


def test_invalid_role_is_rejected(client, docx_bytes):
    response = client.post(
        "/api/analyze",
        files={"file": ("resume.docx", docx_bytes, DOCX)},
        data={"target_role": " "},
    )
    assert response.status_code in {400, 422}


def test_rate_limit_returns_429(docx_bytes):
    settings = Settings(
        _env_file=None,
        environment="test",
        embedder_backend="hash",
        llm_enabled=False,
        rate_limit_per_hour=1,
        rate_limit_per_day=10,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert _analyze(client, docx_bytes).status_code == 200
        second = _analyze(client, docx_bytes)
        assert second.status_code == 429
        assert second.headers["retry-after"]


def test_generic_500_does_not_leak_exception(docx_bytes, settings):
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:

        def boom(*args, **kwargs):
            raise RuntimeError("secret-internal-detail")

        app.state.nlp_analyzer.analyze = boom
        response = _analyze(client, docx_bytes)
        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Analysis failed. Please retry."
        assert "secret-internal-detail" not in response.text
        assert body["request_id"]


def test_cors_preflight(client):
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_trusted_hosts_allow_loopback_healthcheck():
    settings = Settings(
        _env_file=None,
        environment="test",
        embedder_backend="hash",
        llm_enabled=False,
        trusted_hosts="api.example.com",
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health", headers={"host": "localhost"}).status_code == 200
        assert client.get("/api/health", headers={"host": "evil.example.com"}).status_code == 400


def test_consent_blocks_llm_and_keeps_local(docx_bytes):
    settings = Settings(
        _env_file=None,
        environment="test",
        embedder_backend="hash",
        llm_enabled=True,
        opencode_api_key="test-key",
        rate_limit_per_hour=100,
        rate_limit_per_day=100,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = _analyze(client, docx_bytes, consent=False)
        assert response.status_code == 200
        assert response.json()["scoring_source"] == "local_consent"
        assert client.get("/api/config").json()["llm_enabled"] is True


def test_zero_budget_falls_back_to_local(docx_bytes):
    settings = Settings(
        _env_file=None,
        environment="test",
        embedder_backend="hash",
        llm_enabled=True,
        opencode_api_key="test-key",
        llm_max_requests_per_day=0,
        rate_limit_per_hour=100,
        rate_limit_per_day=100,
        log_level="WARNING",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = _analyze(client, docx_bytes, consent=True)
        assert response.status_code == 200
        assert response.json()["scoring_source"] == "local_quota"
