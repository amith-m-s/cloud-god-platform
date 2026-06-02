from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import PaginationMeta


class DocumentResponse(BaseModel):
    id: int
    filename: str
    s3_key: str
    status: str
    tenant_id: str

    model_config = {"from_attributes": True}


class PaginatedDocumentsResponse(BaseModel):
    items: list[DocumentResponse]
    pagination: PaginationMeta


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    tenant_id: str = "default"
    top_k: int = Field(default=5, ge=1, le=50)


class SearchHitResponse(BaseModel):
    chunk_id: int
    document_id: int
    score: float
    text: str
    source: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHitResponse]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    tenant_id: str = "default"
    top_k: int = Field(default=5, ge=1, le=50)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class SeedDocumentRequest(BaseModel):
    document_id: int
    tenant_id: str = "default"
    text: str = Field(min_length=1, max_length=100000)


class SeedDocumentResponse(BaseModel):
    document_id: int
    chunks_created: int
    status: str = "indexed"

