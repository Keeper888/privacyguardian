import os
from typing import List, Optional

from sentence_transformers import SentenceTransformer

_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(name)
    return _model


def embed(text: str) -> List[float]:
    return _get_model().encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    return _get_model().encode(texts, normalize_embeddings=True).tolist()
