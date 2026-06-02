from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.deps import get_db
from app.db.models import Document, User
from app.schemas.common import PaginationMeta
from app.schemas.documents import (
    DocumentResponse,
    PaginatedDocumentsResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SeedDocumentRequest,
    SeedDocumentResponse,
)
from app.services.document_service import index_document_text, save_uploaded_document
from app.services.s3_service import download_bytes_from_s3
from app.services.rag_service import RAGService

router = APIRouter()
logger = structlog.get_logger("documents")
rag = RAGService()


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    doc = save_uploaded_document(
        db=db, file=file, owner_id=current_user.id, tenant_id=tenant_id
    )
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=PaginatedDocumentsResponse)
def list_documents(
    tenant_id: str = "default",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedDocumentsResponse:
    base = db.query(Document).filter(Document.tenant_id == tenant_id)
    total = base.count()
    docs = base.order_by(Document.id.desc()).offset(offset).limit(limit).all()

    return PaginatedDocumentsResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        ),
    )


@router.post("/seed", response_model=SeedDocumentResponse)
def seed_document_text(
    request: SeedDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SeedDocumentResponse:
    """Seed a document with raw text for indexing and search."""
    count = index_document_text(db, request.document_id, request.tenant_id, request.text)
    db.query(Document).filter(Document.id == request.document_id).update({"status": "indexed"})
    db.commit()
    return SeedDocumentResponse(document_id=request.document_id, chunks_created=count)


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    hits = rag.semantic_search(
        db=db, query=request.query, tenant_id=request.tenant_id, top_k=request.top_k
    )
    return SearchResponse(
        query=request.query,
        results=[
            SearchHitResponse(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                score=h.score,
                text=h.text,
                source=h.source,
            )
            for h in hits
        ],
    )


@router.get("/{document_id}/download")
def download_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Download or retrieve the raw document file bytes."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access security scoping check
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access to document is forbidden")

    try:
        payload = download_bytes_from_s3(doc.s3_key)
        return Response(
            content=payload,
            media_type=doc.content_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"inline; filename={doc.filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as exc:
        logger.error("file_download_failed", document_id=document_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to retrieve file from storage")


@router.get("/{document_id}/chunks")
def get_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all text chunks for a document, ordered by chunk_index."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.db.models import Chunk
    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access to document is forbidden")

    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).order_by(Chunk.chunk_index.asc()).all()

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "text": c.text,
            }
            for c in chunks
        ]
    }


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a document, its S3 file, and cascade delete all chunks."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access to document is forbidden")

    from app.services.s3_service import delete_from_s3

    # 1. Delete from S3 (or fallback storage)
    try:
        delete_from_s3(doc.s3_key)
    except Exception as exc:
        logger.warning("s3_delete_failed", key=doc.s3_key, error=str(exc))

    # 2. Delete from DB (chunks cascade delete automatically due to ForeignKey cascade setup)
    db.delete(doc)
    db.commit()

    logger.info("document_deleted", document_id=document_id, filename=doc.filename)
    return Response(status_code=204)
