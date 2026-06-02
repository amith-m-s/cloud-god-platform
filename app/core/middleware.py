from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes.health import REQUEST_COUNT, REQUEST_LATENCY

logger = structlog.get_logger("middleware")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and response, and track Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        request.state.request_id = request_id

        path = request.url.path
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(method=request.method, endpoint=path, status="500").inc()
            REQUEST_LATENCY.labels(endpoint=path).observe(duration)
            raise exc

        duration = time.perf_counter() - start
        duration_ms = round(duration * 1000, 2)

        response.headers["X-Request-ID"] = request_id

        try:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=path,
                status=str(status_code)
            ).inc()
            REQUEST_LATENCY.labels(endpoint=path).observe(duration)
        except Exception as e:
            logger.warning("metrics_recording_failed", error=str(e))

        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=path,
            status=status_code,
            duration_ms=duration_ms,
        )

        return response

