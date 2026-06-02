from __future__ import annotations

import redis
import structlog
from fastapi import APIRouter
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy import text
from starlette.responses import Response

from app.core.config import settings
from app.db.session import engine
from app.schemas.health import HealthResponse, ReadinessDetail, ReadinessResponse

router = APIRouter()
logger = structlog.get_logger("health")

# ── Prometheus metrics (importable by middleware / other modules) ─
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency", ["endpoint"]
)


@router.get("/health", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Liveness probe — returns 200 if the process is alive."""
    return HealthResponse(status="ok", service=settings.app_name)


@router.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    """Readiness probe — checks downstream dependencies."""
    db_ok = _check_database()
    redis_ok = _check_redis()

    if settings.env == "local":
        all_ok = db_ok
        redis_status = "ok" if redis_ok else "mocked"
    else:
        all_ok = db_ok and redis_ok
        redis_status = "ok" if redis_ok else "unavailable"

    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        service=settings.app_name,
        checks=ReadinessDetail(
            database="ok" if db_ok else "unavailable",
            redis=redis_status,
        ),
    )


@router.get("/metrics")
def metrics() -> Response:
    """Prometheus-compatible metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def _check_database() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        return True
    except Exception:
        return False
