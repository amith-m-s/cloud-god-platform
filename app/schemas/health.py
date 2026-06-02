from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "1.0.0"


class ReadinessDetail(BaseModel):
    database: str
    redis: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: ReadinessDetail
