"""VectorRecall + record_fact embedding hook (P8.10)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.memory.embeddings import EmbeddingResult
from app.memory.embeddings.factory import (
    build_embeddings_provider,
    set_default_provider,
)
from app.memory.facts import record_fact
from app.memory.recall_factory import build_recall
from app.memory.vector_recall import VectorRecall, cosine_similarity

pytestmark = pytest.mark.usefixtures("override_db")


class DictProvider:
    """Deterministic fake: returns a canned vector per input substring."""

    name = "fake"
    model = "fake-1"

    def __init__(self, table: dict[str, list[float]]) -> None:
        self._table = table

    def embed(self, text: str) -> EmbeddingResult | None:
        text = (text or "").lower()
        for needle, vec in self._table.items():
            if needle in text:
                return EmbeddingResult(vector=vec, model=self.model, dimensions=len(vec))
        return EmbeddingResult(
            vector=[0.0] * 3, model=self.model, dimensions=3
        )


@pytest.fixture
def fake_provider():
    # Keys deliberately distinct from words that appear in the canonical
    # _fact_embed_text synthesis (which always mentions "tax year …").
    p = DictProvider(
        {
            "salary": [1.0, 0.0, 0.0],
            "liability": [0.0, 1.0, 0.0],
            "receipt": [0.0, 0.0, 1.0],
        }
    )
    set_default_provider(p)
    build_embeddings_provider.cache_clear()
    yield p
    set_default_provider(None)
    build_embeddings_provider.cache_clear()


def test_cosine_similarity_identity_and_orthogonal() -> None:
    assert cosine_similarity([1.0, 0, 0], [1.0, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0, 0], [0, 1.0, 0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0


def test_cosine_similarity_handles_zero_vectors() -> None:
    assert cosine_similarity([0, 0, 0], [1, 1, 1]) == 0.0


def test_record_fact_attaches_embedding_when_provider_live(db_session, fake_provider) -> None:
    fact = record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="annual_gross_income",
        value=Decimal("5000000"),
        label="Globacom salary",
    )
    db_session.commit()
    assert fact.embedding_json is not None
    vector = json.loads(fact.embedding_json)
    assert vector == [1.0, 0.0, 0.0]  # matched on 'salary'
    assert fact.embedding_model == "fake-1"
    assert fact.embedding_dim == 3


def test_vector_recall_ranks_by_cosine(db_session, fake_provider) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2024,
        fact_type="annual_gross_income",
        value=Decimal("4_000_000"),
        label="Globacom salary",
    )
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="total_tax",
        value=Decimal("560_000"),
        label="PIT liability",
    )
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="nrs_submission_status",
        value="accepted",
        label="NRS receipt",
    )
    db_session.commit()

    recall = VectorRecall(db_session, provider=fake_provider)
    hits = recall.recall(user_nin_hash="h", query="what was my liability?")
    # 'liability' returns the [0,1,0] bucket → total_tax should rank first.
    assert hits[0].fact_type == "total_tax"


def test_vector_recall_user_scoping(db_session, fake_provider) -> None:
    record_fact(
        db_session,
        user_nin_hash="alice",
        tax_year=2025,
        fact_type="annual_gross_income",
        value=Decimal("1"),
        label="alice salary",
    )
    record_fact(
        db_session,
        user_nin_hash="bob",
        tax_year=2025,
        fact_type="annual_gross_income",
        value=Decimal("1"),
        label="bob salary",
    )
    db_session.commit()

    recall = VectorRecall(db_session, provider=fake_provider)
    hits = recall.recall(user_nin_hash="alice", query="salary")
    assert all(h.user_nin_hash == "alice" for h in hits)


def test_vector_recall_skips_rows_without_embeddings(db_session) -> None:
    """No provider = rows lack embedding_json; vector recall returns nothing."""
    set_default_provider(None)
    build_embeddings_provider.cache_clear()

    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="annual_gross_income",
        value=Decimal("5000000"),
    )
    db_session.commit()
    # VectorRecall directly with the (noop) factory provider:
    recall = VectorRecall(db_session)
    assert recall.recall(user_nin_hash="h", query="anything") == []


def test_build_recall_returns_keyword_when_no_embeddings(db_session) -> None:
    set_default_provider(None)
    build_embeddings_provider.cache_clear()
    recall = build_recall(db_session)
    assert recall.__class__.__name__ == "KeywordRecall"


def test_build_recall_returns_vector_when_embeddings_live(db_session, fake_provider) -> None:
    recall = build_recall(db_session)
    assert recall.__class__.__name__ == "VectorRecall"
