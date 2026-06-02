from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RequestIdMiddleware
from app.db.session import init_db
from app.services.queue_service import ensure_queue_exists
from app.services.s3_service import ensure_bucket_exists

logger = structlog.get_logger("app")

# ── Rate limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging(settings.log_level)
    logger.info("starting", app=settings.app_name, env=settings.env)
    init_db()
    # Ensure LocalStack resources exist in local dev
    if settings.aws_endpoint_url:
        try:
            ensure_bucket_exists()
            queue_url = ensure_queue_exists()
            if queue_url:
                settings.__dict__["sqs_queue_url"] = queue_url
                logger.info("sqs_queue_initialized", url=queue_url)
        except Exception as exc:
            logger.warning("localstack_init_skipped", error=str(exc))
    logger.info("startup_complete")
    yield
    logger.info("shutdown_complete")


# ── OpenAPI tag metadata ─────────────────────────────────────
tags_metadata = [
    {
        "name": "system",
        "description": "Health checks, readiness probes, and Prometheus metrics for monitoring and orchestration.",
    },
    {
        "name": "auth",
        "description": "User registration, JWT authentication, token refresh, and profile management.",
    },
    {
        "name": "documents",
        "description": "Multi-tenant document upload, listing, semantic indexing, and full-text search.",
    },
    {
        "name": "rag",
        "description": "Retrieval-Augmented Generation — ask questions against your uploaded knowledge base.",
    },
]


app = FastAPI(
    title="☁️ Cloud God Platform",
    version="1.0.0",
    summary="Production-grade AWS cloud platform with document intelligence.",
    description=(
        "## Overview\n\n"
        "Cloud God Platform is a FAANG-grade, multi-tenant document intelligence system "
        "built on FastAPI, PostgreSQL, Redis, S3, and SQS.\n\n"
        "### Key Capabilities\n\n"
        "- **JWT Authentication** — Secure registration, login, and token refresh\n"
        "- **Document Pipeline** — Upload, chunk, embed, and index documents per tenant\n"
        "- **Semantic Search** — TF-IDF powered search across your knowledge base\n"
        "- **RAG Chat** — Ask questions and get context-aware answers from your docs\n"
        "- **Observability** — Structured logging, Prometheus metrics, request ID tracing\n"
    ),
    contact={
        "name": "Cloud God Engineering",
        "email": "engineering@cloudgod.io",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Rate limiter state ───────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Middleware (order matters — last added runs first) ───────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)

# ── Routes ───────────────────────────────────────────────────
# System routes (no prefix — standard for probes)
app.include_router(health_router, tags=["system"])

# API v1 routes
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(chat_router, prefix="/api/v1", tags=["rag"])

# ── Frontend ─────────────────────────────────────────────────
_frontend_dir = pathlib.Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(str(_frontend_dir / "index.html"))


# ── Global exception handlers ────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        errors.append(f"{loc}: {err.get('msg', 'invalid')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )
