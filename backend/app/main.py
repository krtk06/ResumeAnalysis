from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .ml import Embedder, build_embedder
from .routes.analyze import router as analyze_router
from .services.llm_scorer import LLMScorer
from .services.matcher import Calibrator, RoleMatcher
from .services.nlp_analyzer import NLPAnalyzer
from .services.rate_limit import LLMBudget, SlidingWindowLimiter
from .services.taxonomy import get_roles, get_taxonomy

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(
    settings: Settings | None = None,
    *,
    embedder: Embedder | None = None,
    llm_scorer: LLMScorer | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        taxonomy = get_taxonomy()
        roles = get_roles()
        active_embedder = embedder or build_embedder(settings)
        matcher = RoleMatcher(
            taxonomy=taxonomy,
            roles=roles,
            embedder=active_embedder,
            calibrator=Calibrator.from_path(settings.calibration_path),
        )
        scorer = llm_scorer or LLMScorer(settings)
        app.state.settings = settings
        app.state.taxonomy = taxonomy
        app.state.roles = roles
        app.state.nlp_analyzer = NLPAnalyzer(taxonomy)
        app.state.embedder = active_embedder
        app.state.matcher = matcher
        app.state.llm_scorer = scorer
        app.state.llm_budget = LLMBudget(
            settings.llm_max_requests_per_day,
            settings.llm_monthly_allowance_usd,
        )
        app.state.rate_limiter = SlidingWindowLimiter(
            settings.rate_limit_per_hour,
            settings.rate_limit_per_day,
        )
        logger.info(
            "startup embedder=%s degraded=%s llm_configured=%s roles=%d",
            active_embedder.name,
            active_embedder.degraded,
            settings.llm_configured,
            len(roles),
        )
        try:
            yield
        finally:
            close = getattr(scorer, "aclose", None)
            if close is not None:
                await close()

    app = FastAPI(
        title=settings.app_name,
        description="Evidence-backed resume analysis and role matching.",
        version=settings.version,
        lifespan=lifespan,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_origin_regex=settings.cors_origin_regex,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID", "X-Session-ID"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )

    if settings.trusted_host_list and settings.trusted_host_list != ["*"]:
        # Container and load-balancer healthchecks connect over loopback with a
        # 127.0.0.1 Host header. Keep those working while still rejecting
        # arbitrary external Host headers.
        allowed_hosts = list(settings.trusted_host_list)
        for loopback in ("127.0.0.1", "localhost", "[::1]"):
            if loopback not in allowed_hosts:
                allowed_hosts.append(loopback)
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        headers = dict(exc.headers or {})
        headers["X-Request-ID"] = request_id
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id},
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
        logger.exception("Unhandled error request_id=%s: %s", request_id, exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Analysis failed. Please retry.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    app.include_router(analyze_router, prefix="/api", tags=["Analysis"])

    @app.get("/")
    async def root():
        return {
            "message": "Resume Analysis API",
            "version": settings.version,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
