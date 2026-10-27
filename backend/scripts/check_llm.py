"""Smoke-test the configured OpenCode Go endpoint.

Usage:
    cd backend
    python scripts/check_llm.py

The key is read from the environment/.env and is never printed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import AsyncOpenAI  # noqa: E402

from app.config import Settings  # noqa: E402


async def main() -> int:
    settings = Settings()
    if not settings.llm_configured:
        print("LLM is not configured. Set LLM_ENABLED=true and OPENCODE_API_KEY.")
        return 2

    assert settings.opencode_api_key is not None
    client = AsyncOpenAI(
        api_key=settings.opencode_api_key.get_secret_value(),
        base_url=settings.opencode_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
        default_headers={"User-Agent": settings.opencode_user_agent},
    )
    try:
        response = await client.chat.completions.create(
            model=settings.opencode_model,
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": 'Return {"ok": true}.'},
            ],
            temperature=0,
            max_tokens=20,
            response_format={"type": "json_object"},
            extra_headers={"x-opencode-session": "deploy-smoke-test"},
        )
        payload = response.model_dump()
        print("model:", settings.opencode_model)
        print("base_url:", settings.opencode_base_url)
        print("content:", response.choices[0].message.content)
        print("usage:", payload.get("usage"))
        return 0
    except Exception as exc:
        print(f"OpenCode Go call failed for {settings.opencode_model}: {exc}")
        print("If this is 403/404, try OPENCODE_FALLBACK_MODEL=glm-5.3-flash.")
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
