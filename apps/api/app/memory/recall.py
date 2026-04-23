"""Memory recall (P8.3).

Abstract over "find facts the user has been talking about" so that when
the owner picks an embeddings provider, swapping from keyword to vector
recall is a factory flip.

v1 ships `KeywordRecall` — a pure SQL LIKE match over the label + the
stringified value + meta. Works on SQLite and Postgres. No external deps.

The `MemoryRecall` Protocol lets tests and future `VectorRecall`
implementations share one contract.
"""

from __future__ import annotations

import re
from typing import Protocol

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import YearlyFact


_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def _tokens(query: str) -> list[str]:
    return [t for t in _NON_WORD.sub(" ", query.lower()).split() if t]


class MemoryRecall(Protocol):
    """Return YearlyFacts matching a free-text `query` for one taxpayer."""

    def recall(
        self,
        *,
        user_nin_hash: str | None,
        query: str,
        limit: int = 10,
    ) -> list[YearlyFact]: ...


class KeywordRecall:
    """SQL LIKE over label + value + meta (stringified).

    Scoring is simple: more tokens matched in more columns = higher rank.
    Ties fall back to most-recently recorded.
    """

    def __init__(self, session: Session) -> None:
        self._s = session

    def recall(
        self,
        *,
        user_nin_hash: str | None,
        query: str,
        limit: int = 10,
    ) -> list[YearlyFact]:
        tokens = _tokens(query)
        if not tokens:
            return []

        q = self._s.query(YearlyFact)
        if user_nin_hash is not None:
            q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)

        # Portable substring search: SQLite LIKE is case-insensitive for
        # ASCII by default; Postgres gets ILIKE behavior by lowering both
        # sides via `func.lower` — we already lowered tokens, and the
        # columns we search are typically ASCII values / fact types.
        clauses = []
        for token in tokens:
            like = f"%{token}%"
            clauses.append(
                or_(
                    YearlyFact.fact_type.ilike(like),
                    YearlyFact.label.ilike(like),
                    YearlyFact.value.ilike(like),
                    YearlyFact.source.ilike(like),
                )
            )
        # Facts must match at least one token to appear; we rank later.
        q = q.filter(or_(*clauses))

        rows = q.order_by(YearlyFact.recorded_at.desc()).limit(
            max(1, min(limit * 4, 200))
        ).all()

        ranked = sorted(
            rows,
            key=lambda r: (-_score(r, tokens), -r.recorded_at.timestamp()),
        )
        return ranked[:limit]


def _score(fact: YearlyFact, tokens: list[str]) -> int:
    haystack = " ".join(
        filter(
            None,
            [
                fact.fact_type or "",
                fact.label or "",
                fact.value or "",
                fact.source or "",
            ],
        )
    ).lower()
    return sum(1 for t in tokens if t in haystack)
