from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.queue_service import enqueue_document_job
from app.services.s3_service import upload_bytes_to_s3

logger = structlog.get_logger("document_service")


def _split_text(text: str, chunk_size: int = 900) -> list[str]:
    """Split text into overlapping chunks for better retrieval."""
    text = " ".join(text.split())
    if not text:
        return []
    overlap = min(100, chunk_size // 4)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def save_uploaded_document(
    db: Session, file: UploadFile, owner_id: int, tenant_id: str
) -> Document:
    payload = file.file.read()
    safe_name = file.filename or "document.bin"
    s3_key = f"{tenant_id}/{uuid4()}_{safe_name}"

    upload_bytes_to_s3(s3_key, payload, file.content_type)

    doc = Document(
        tenant_id=tenant_id,
        owner_id=owner_id,
        filename=safe_name,
        s3_key=s3_key,
        content_type=file.content_type,
        status="queued",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info("document_saved", document_id=doc.id, filename=safe_name, tenant=tenant_id)
    enqueue_document_job(doc.id, tenant_id, s3_key)
    return doc


def index_document_text(
    db: Session, document_id: int, tenant_id: str, text: str
) -> int:
    chunks = _split_text(text)
    for idx, chunk_text in enumerate(chunks):
        db.add(
            Chunk(
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_index=idx,
                text=chunk_text,
                vector_id=None,
            )
        )
    db.commit()
    logger.info("document_indexed", document_id=document_id, chunks=len(chunks))
    return len(chunks)
