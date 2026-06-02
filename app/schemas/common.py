from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standardized error envelope returned by all error handlers."""
    detail: str
    request_id: str | None = None


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
