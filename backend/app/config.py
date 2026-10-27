from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Resume Analysis API"
    version: str = "2.0.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # HTTP / CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    cors_origin_regex: str | None = None
    trusted_hosts: str = "*"
    trust_proxy_headers: bool = False

    # Uploads
    max_upload_mb: int = 10
    max_pages: int = 10
    max_jd_chars: int = 10_000
    max_resume_chars_for_llm: int = 6_000

    # Embeddings
    model_name: str = "all-MiniLM-L6-v2"
    embedder_backend: Literal["auto", "fastembed", "sentence-transformers", "hash"] = "auto"
    fastembed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedder_cache_dir: str | None = None

    # LLM: OpenCode Go
    llm_enabled: bool = False
    llm_provider: Literal["opencode_go", "local"] = "opencode_go"
    opencode_api_key: SecretStr | None = None
    opencode_base_url: str = "https://opencode.ai/inference/go/openai/v1"
    opencode_model: str = "beam-free"
    opencode_fallback_model: str = "glm-5.3-flash"
    opencode_user_agent: str = "resume-analysis/2.0"
    opencode_allow_paid_fallback: bool = False
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 1
    llm_max_requests_per_day: int = 50
    llm_monthly_allowance_usd: float = 50.0
    require_consent: bool = True

    # Rate limiting
    rate_limit_per_hour: int = 10
    rate_limit_per_day: int = 50

    # Calibration (optional JSON produced by eval/calibrate.py)
    calibration_path: str | None = None

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "local":
            return False
        if not (self.llm_enabled and self.opencode_api_key):
            return False
        # The paid-fallback switch is a hard guard: a non-Go base URL can bill
        # the OpenCode Console per request. Refuse to start the LLM path unless
        # the operator explicitly opts in.
        return self.opencode_allow_paid_fallback or "opencode.ai/inference/go" in self.opencode_base_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
