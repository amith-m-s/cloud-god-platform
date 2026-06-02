from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np


@dataclass
class EmbeddingResult:
    vector: list[float]


class EmbeddingService:
    """
    Deterministic local embedding for development and testing.
    Replace with OpenAI / Ollama / sentence-transformers in production.
    """

    def embed(self, text: str, dimension: int = 384) -> EmbeddingResult:
        digest = sha256(text.encode("utf-8")).digest()
        raw = np.frombuffer(
            digest * ((dimension // len(digest)) + 1), dtype=np.uint8
        )[:dimension]
        vector = (raw.astype(np.float32) / 255.0).tolist()
        return EmbeddingResult(vector=vector)

    def embed_batch(self, texts: list[str], dimension: int = 384) -> list[EmbeddingResult]:
        return [self.embed(t, dimension) for t in texts]
