"""KeywordRecall tests (P8.3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.memory.facts import record_fact
from app.memory.recall import KeywordRecall

pytestmark = pytest.mark.usefixtures("override_db")


def _seed(db_session) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2024,
        fact_type="annual_gross_income",
        value=Decimal("4000000"),
        label="2024 gross from Globacom",
        source="filing",
    )
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="total_tax",
        value=Decimal("560000"),
        label="2025 PIT payable",
        source="filing",
    )
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="nrs_submission_status",
        value="accepted",
        label="2025 NRS accepted",
        source="filing",
    )
    record_fact(
        db_session,
        user_nin_hash="other",
        tax_year=2025,
        fact_type="annual_gross_income",
        value=Decimal("999"),
        label="someone else's fact",
        source="filing",
    )
    db_session.commit()


def test_keyword_recall_matches_label(db_session) -> None:
    _seed(db_session)
    recaller = KeywordRecall(db_session)
    hits = recaller.recall(user_nin_hash="h", query="gross")
    assert len(hits) == 1
    assert hits[0].label == "2024 gross from Globacom"


def test_keyword_recall_scopes_by_user(db_session) -> None:
    _seed(db_session)
    recaller = KeywordRecall(db_session)
    hits = recaller.recall(user_nin_hash="h", query="income")
    assert all(r.user_nin_hash == "h" for r in hits)
    # 'other' user's fact is excluded.
    assert not any(r.user_nin_hash == "other" for r in hits)


def test_keyword_recall_ranks_by_token_coverage(db_session) -> None:
    _seed(db_session)
    recaller = KeywordRecall(db_session)
    hits = recaller.recall(user_nin_hash="h", query="PIT payable")
    # Label has both tokens → ranked first.
    assert hits[0].fact_type == "total_tax"


def test_keyword_recall_empty_query_returns_nothing(db_session) -> None:
    _seed(db_session)
    recaller = KeywordRecall(db_session)
    assert recaller.recall(user_nin_hash="h", query="   ") == []


def test_keyword_recall_no_match_returns_empty_list(db_session) -> None:
    _seed(db_session)
    recaller = KeywordRecall(db_session)
    assert recaller.recall(user_nin_hash="h", query="bitcoin") == []
