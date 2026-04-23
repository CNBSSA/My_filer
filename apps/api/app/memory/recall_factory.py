"""Pick the active MemoryRecall based on embeddings availability."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.memory.embeddings.factory import is_embeddings_enabled
from app.memory.recall import KeywordRecall, MemoryRecall
from app.memory.vector_recall import VectorRecall


def build_recall(session: Session) -> MemoryRecall:
    """Return VectorRecall when embeddings are enabled, KeywordRecall else."""
    if is_embeddings_enabled():
        return VectorRecall(session)
    return KeywordRecall(session)
