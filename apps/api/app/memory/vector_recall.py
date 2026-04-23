"""Semantic recall over YearlyFact embeddings (P8.10).

Implements the same `MemoryRecall` shape as `KeywordRecall`. Storage is
a JSON-encoded float array in `yearly_facts.embedding_json`, which keeps
the implementation portable across SQLite (dev / tests) and Postgres
(prod without pgvector today, pgvector later).

Ranking is cosine similarity; the provider's embedding for the query is
computed once per call. We scope by `user_nin_hash` so the SQL narrows
the row set before Python does the dot products.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import YearlyFact
from app.memory.embeddings.base import EmbeddingsError, EmbeddingsProvider
from app.memory.embeddings.factory import build_embeddings_provider

log = logging.getLogger("mai_filer.memory.vector")


@dataclass
class ScoredFact:
    fact: YearlyFact
    similarity: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class VectorRecall:
    """Cosine similarity over the active EmbeddingsProvider's vectors."""

    def __init__(
        self,
        session: Session,
        *,
        provider: EmbeddingsProvider | None = None,
    ) -> None:
        self._s = session
        self._provider = provider or build_embeddings_provider()

    def recall(
        self,
        *,
        user_nin_hash: str | None,
        query: str,
        limit: int = 10,
    ) -> list[YearlyFact]:
        query = (query or "").strip()
        if not query:
            return []

        try:
            embedding = self._provider.embed(query)
        except EmbeddingsError as exc:
            log.warning("embeddings provider failed; falling back empty: %s", exc)
            return []
        if embedding is None:
            # Noop or empty — caller should route to KeywordRecall.
            return []

        query_vec = embedding.vector

        q = self._s.query(YearlyFact).filter(YearlyFact.embedding_json.is_not(None))
        if user_nin_hash is not None:
            q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)

        # Keep the scan bounded — we're doing Python-side math, so we cap
        # at a reasonable per-user working set. Users with > 2000 vectored
        # facts probably want pgvector anyway, which is a later migration.
        rows = q.order_by(YearlyFact.recorded_at.desc()).limit(2000).all()

        scored: list[ScoredFact] = []
        for row in rows:
            try:
                vec = json.loads(row.embedding_json or "[]")
            except json.JSONDecodeError:
                continue
            if not isinstance(vec, list) or not vec:
                continue
            # Dimension mismatch = different model; skip rather than distort.
            if len(vec) != len(query_vec):
                continue
            scored.append(ScoredFact(row, cosine_similarity(query_vec, vec)))

        scored.sort(key=lambda s: (-s.similarity, -s.fact.recorded_at.timestamp()))
        return [s.fact for s in scored[:limit]]
