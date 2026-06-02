from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.deps import get_db
from app.db.models import User
from app.schemas.documents import ChatRequest, ChatResponse
from app.services.rag_service import RAGService

router = APIRouter()
rag = RAGService()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    hits = rag.semantic_search(
        db=db,
        query=request.question,
        tenant_id=request.tenant_id,
        top_k=request.top_k,
    )
    answer, sources = rag.build_answer(request.question, hits)
    return ChatResponse(answer=answer, sources=sources)


from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream tokenized context-aware responses in real-time."""
    hits = rag.semantic_search(
        db=db,
        query=request.question,
        tenant_id=request.tenant_id,
        top_k=request.top_k,
    )
    return StreamingResponse(
        rag.stream_answer(request.question, hits),
        media_type="text/event-stream"
    )
