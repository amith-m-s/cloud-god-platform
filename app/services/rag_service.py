from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.embedding_service import EmbeddingService

logger = structlog.get_logger("rag_service")


@dataclass
class SearchHit:
    chunk_id: int
    document_id: int
    score: float
    text: str
    source: str


class RAGService:
    def __init__(self) -> None:
        self.embedder = EmbeddingService()

    def semantic_search(
        self, db: Session, query: str, tenant_id: str, top_k: int = 5
    ) -> list[SearchHit]:
        """TF-IDF inspired scoring — a step above raw word overlap."""
        tokens = [t.lower() for t in query.split() if len(t) > 2]
        if not tokens:
            return []

        rows = db.execute(
            select(Chunk, Document.filename)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.tenant_id == tenant_id)
        ).all()

        if not rows:
            return []

        total_docs = len(rows)
        # document frequency for each token
        doc_freq: Counter[str] = Counter()
        for chunk, _ in rows:
            hay = chunk.text.lower()
            for t in set(tokens):
                if t in hay:
                    doc_freq[t] += 1

        results: list[SearchHit] = []
        for chunk, filename in rows:
            hay = chunk.text.lower()
            score = 0.0
            for t in tokens:
                if t in hay:
                    tf = hay.count(t) / max(len(hay.split()), 1)
                    idf = math.log((total_docs + 1) / (doc_freq.get(t, 0) + 1)) + 1
                    score += tf * idf
            if score > 0:
                results.append(
                    SearchHit(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        score=round(score, 4),
                        text=chunk.text,
                        source=filename,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        logger.info("search_completed", query=query[:80], hits=len(results), returned=min(top_k, len(results)))
        return results[:top_k]

    def build_answer(
        self, question: str, hits: Iterable[SearchHit]
    ) -> tuple[str, list[str]]:
        import httpx
        import re
        from app.core.config import settings

        hits = list(hits)
        if not hits:
            return (
                "🔍 **System Notification**\n\n"
                "I searched the active database but could not find any document context matching your query. "
                "Please upload a document containing the relevant text or seed the knowledge base first.",
                []
            )

        sources = sorted(list(set(hit.source for hit in hits)))
        context_text = "\n\n".join([f"Source: {hit.source}\nContent: {hit.text}" for hit in hits])

        llm_success = False
        answer = ""

        # 1. Try OpenAI if key is present
        if settings.openai_api_key:
            try:
                logger.info("llm_call_start", provider="openai")
                headers = {
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are Cloud God AI, an advanced document intelligence assistant. "
                                "Answer the user's question using the provided context chunks. "
                                "Format your response beautifully with markdown, bolding key points and using structured lists or code highlights where relevant. "
                                "Always quote relevant sources if possible."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Context Chunks:\n{context_text}\n\nQuestion: {question}"
                        }
                    ],
                    "temperature": 0.3
                }
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["choices"][0]["message"]["content"]
                        llm_success = True
                        logger.info("llm_call_success", provider="openai")
                    else:
                        logger.warning("llm_call_failed", provider="openai", status=resp.status_code, text=resp.text)
            except Exception as e:
                logger.error("llm_call_exception", provider="openai", error=str(e))

        # 2. Try Ollama if provider is ollama
        if not llm_success and settings.llm_provider == "ollama" and settings.ollama_base_url:
            try:
                logger.info("llm_call_start", provider="ollama")
                payload = {
                    "model": settings.chat_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are Cloud God AI, an advanced document intelligence assistant. Answer the user's question using the provided context. Use clean markdown."
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context_text}\n\nQuestion: {question}"
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data["message"]["content"]
                        llm_success = True
                        logger.info("llm_call_success", provider="ollama")
                    else:
                        logger.warning("llm_call_failed", provider="ollama", status=resp.status_code, text=resp.text)
            except Exception as e:
                logger.error("llm_call_exception", provider="ollama", error=str(e))

        # 3. Dynamic Fallback: highly realistic context synthesizer (looks and feels like a real LLM response)
        if not llm_success:
            logger.info("llm_fallback_synthesizer_activated")
            
            q_words = [w.lower() for w in question.split() if len(w) > 3]
            bullets = []
            
            # Smart extraction: split text chunks into sentences and pull matches or strong sentences
            for hit in hits:
                sentences = re.split(r'(?<=[.!?])\s+', hit.text)
                for s in sentences:
                    s_clean = s.strip()
                    if len(s_clean) < 15:
                        continue
                    # Prioritize sentences mentioning query keywords
                    score = sum(1 for w in q_words if w in s_clean.lower())
                    if score > 0:
                        bullets.append((score, s_clean, hit.source))
                    else:
                        # Baseline score for generic sentences
                        bullets.append((0, s_clean, hit.source))
            
            # Sort by keyword match score, then length
            bullets.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
            
            # Take top unique sentences
            selected_bullets = []
            seen = set()
            for score, text, src in bullets:
                norm = text.lower()[:30]
                if norm not in seen:
                    seen.add(norm)
                    selected_bullets.append((text, src))
                if len(selected_bullets) >= 4:
                    break
            
            if selected_bullets:
                bullet_str = "\n".join([f"- **Key Insight**: \"{txt}\" *(Source: `{src}`)*" for txt, src in selected_bullets])
            else:
                bullet_str = "\n".join([f"- **Context segment**: \"{hit.text[:200]}...\" *(Source: `{hit.source}`)*" for hit in hits[:3]])

            # Formulate structured markdown response
            answer = (
                "🤖 **Cloud God AI (Dynamic Context Synthesizer)**\n\n"
                f"I processed **{len(hits)} relevant context segments** from your document database to answer: *\"{question}\"*\n\n"
                "### 📋 Synthesis & Analysis\n"
                "Based on the ingested document chunks, the following data points were identified:\n\n"
                f"{bullet_str}\n\n"
                "### 🏗️ Inference & Reasoning\n"
                f"The matching documents show clear references regarding your query. The semantic relevance score peaks at "
                f"**{hits[0].score:.4f}** (source: `{hits[0].source}`).\n\n"
                "> 💡 **System Note**: To enable true generative answering using a language model, configure a valid `OPENAI_API_KEY` "
                "or connect a local `Ollama` instance in your environment configuration (`.env` file)."
            )

        return answer, sources

    def stream_answer(
        self, question: str, hits: list[SearchHit]
    ) -> Iterable[str]:
        import json
        import time
        import httpx
        from app.core.config import settings

        if not hits:
            error_msg = json.dumps({
                'type': 'token',
                'token': '🔍 **System Notification**\n\nI searched the active database but could not find any document context matching your query. Please upload a document containing the relevant text or seed the knowledge base first.'
            })
            yield f"data: {error_msg}\n\n"
            sources_msg = json.dumps({'type': 'sources', 'sources': []})
            yield f"data: {sources_msg}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return

        sources = sorted(list(set(hit.source for hit in hits)))
        sources_msg = json.dumps({'type': 'sources', 'sources': sources})
        yield f"data: {sources_msg}\n\n"
        time.sleep(0.05)

        context_text = "\n\n".join([f"Source: {hit.source}\nContent: {hit.text}" for hit in hits])

        llm_success = False

        # 1. Try OpenAI if key is present
        if settings.openai_api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are Cloud God AI, an advanced document intelligence assistant. "
                                "Answer the user's question using the provided context chunks. "
                                "Format your response beautifully with markdown, bolding key points and using structured lists or code highlights where relevant. "
                                "Always quote relevant sources if possible."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Context Chunks:\n{context_text}\n\nQuestion: {question}"
                        }
                    ],
                    "stream": True,
                    "temperature": 0.3
                }
                with httpx.Client(timeout=30.0) as client:
                    with client.stream("POST", "https://api.openai.com/v1/chat/completions", headers=headers, json=payload) as response:
                        if response.status_code == 200:
                            llm_success = True
                            for line in response.iter_lines():
                                if not line.strip():
                                    continue
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk_data = json.loads(data_str)
                                        token = chunk_data["choices"][0]["delta"].get("content", "")
                                        if token:
                                            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                                    except Exception:
                                        pass
                        else:
                            logger.warning("llm_stream_failed", provider="openai", status=response.status_code)
            except Exception as e:
                logger.error("llm_stream_exception", provider="openai", error=str(e))

        # 2. Try Ollama if provider is ollama
        if not llm_success and settings.llm_provider == "ollama" and settings.ollama_base_url:
            try:
                payload = {
                    "model": settings.chat_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are Cloud God AI, an advanced document intelligence assistant. Answer the user's question using the provided context. Use clean markdown."
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context_text}\n\nQuestion: {question}"
                        }
                    ],
                    "stream": True,
                    "options": {"temperature": 0.3}
                }
                with httpx.Client(timeout=30.0) as client:
                    with client.stream("POST", f"{settings.ollama_base_url}/api/chat", json=payload) as response:
                        if response.status_code == 200:
                            llm_success = True
                            for line in response.iter_lines():
                                if not line.strip():
                                    continue
                                try:
                                    chunk_data = json.loads(line)
                                    token = chunk_data["message"].get("content", "")
                                    if token:
                                        yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                                except Exception:
                                    pass
                        else:
                            logger.warning("llm_stream_failed", provider="ollama", status=response.status_code)
            except Exception as e:
                logger.error("llm_stream_exception", provider="ollama", error=str(e))

        # 3. Dynamic Fallback: highly realistic context synthesizer (yield tokens at natural reading pace)
        if not llm_success:
            import re
            bullets = []
            q_words = [w.lower() for w in question.split() if len(w) > 3]
            for hit in hits:
                sentences = re.split(r'(?<=[.!?])\s+', hit.text)
                for s in sentences:
                    s_clean = s.strip()
                    if len(s_clean) < 15:
                        continue
                    score = sum(1 for w in q_words if w in s_clean.lower())
                    bullets.append((score, s_clean, hit.source))
            
            bullets.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
            
            selected_bullets = []
            seen = set()
            for score, text, src in bullets:
                norm = text.lower()[:30]
                if norm not in seen:
                    seen.add(norm)
                    selected_bullets.append((text, src))
                if len(selected_bullets) >= 4:
                    break
            
            if selected_bullets:
                bullet_str = "\n".join([f"- **Key Insight**: \"{txt}\" *(Source: `{src}`)*" for txt, src in selected_bullets])
            else:
                bullet_str = "\n".join([f"- **Context segment**: \"{hit.text[:200]}...\" *(Source: `{hit.source}`)*" for hit in hits[:3]])

            full_answer = (
                "🤖 **Cloud God AI (Dynamic Context Synthesizer Stream)**\n\n"
                f"I processed **{len(hits)} relevant context segments** from your document database to answer: *\"{question}\"*\n\n"
                "### 📋 Synthesis & Analysis\n"
                "Based on the ingested document chunks, the following data points were identified:\n\n"
                f"{bullet_str}\n\n"
                "### 🏗️ Inference & Reasoning\n"
                f"The matching documents show clear references regarding your query. The semantic relevance score peaks at "
                f"**{hits[0].score:.4f}** (source: `{hits[0].source}`).\n\n"
                "> 💡 **System Note**: To enable true generative token streaming using a language model, configure a valid `OPENAI_API_KEY` "
                "or connect a local `Ollama` instance in your environment configuration (`.env` file)."
            )
            
            words = full_answer.split(" ")
            chunk_size = 3
            for i in range(0, len(words), chunk_size):
                token = " ".join(words[i:i+chunk_size]) + " "
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                time.sleep(0.04)

        yield "data: {\"type\": \"done\"}\n\n"
