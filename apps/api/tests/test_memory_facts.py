"""YearlyFact repository tests (P8.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.db.models import Filing, YearlyFact
from app.memory.facts import fact_to_dict, list_facts, record_fact, record_filing_facts

pytestmark = pytest.mark.usefixtures("override_db")


def test_record_fact_stringifies_decimal(db_session) -> None:
    fact = record_fact(
        db_session,
        user_nin_hash="hash-1",
        tax_year=2026,
        fact_type="annual_gross_income",
        value=Decimal("5000000.00"),
    )
    db_session.commit()
    assert fact.value == "5000000.00"
    assert fact.value_kind == "decimal"
    assert fact.unit == "NGN"


def test_record_fact_handles_count_and_text(db_session) -> None:
    record_fact(
        db_session,
        user_nin_hash="hash-1",
        tax_year=2026,
        fact_type="income_source_count",
        value=3,
        unit="n",
    )
    record_fact(
        db_session,
        user_nin_hash="hash-1",
        tax_year=2026,
        fact_type="nrs_submission_status",
        value="accepted",
        unit="status",
    )
    db_session.commit()
    rows = list_facts(db_session, user_nin_hash="hash-1", tax_year=2026)
    kinds = {r.fact_type: r.value_kind for r in rows}
    assert kinds["income_source_count"] == "count"
    assert kinds["nrs_submission_status"] == "text"


def test_list_facts_filters_and_orders_recent_first(db_session) -> None:
    for year in (2024, 2025, 2026):
        record_fact(
            db_session,
            user_nin_hash="hash-2",
            tax_year=year,
            fact_type="annual_gross_income",
            value=Decimal(f"{year * 1000}"),
        )
    db_session.commit()
    rows = list_facts(db_session, user_nin_hash="hash-2")
    assert [r.tax_year for r in rows] == [2026, 2025, 2024]


def _filing_return(tax_year: int, gross: str, tax: str) -> dict:
    return {
        "tax_year": tax_year,
        "total_gross_income": gross,
        "paye_already_withheld": "100000.00",
        "net_payable": "50000.00",
        "computation": {
            "total_deductions": "500000.00",
            "chargeable_income": gross,
            "total_tax": tax,
            "effective_rate": "0.1380",
        },
        "income_sources": [{"kind": "employment"}, {"kind": "rental"}],
        "supporting_document_ids": ["doc-1"],
    }


def test_record_filing_facts_captures_salient_numbers(db_session) -> None:
    filing = Filing(
        tax_year=2026,
        return_json=_filing_return(2026, "5000000.00", "690000.00"),
        audit_status="green",
        submission_status="accepted",
        nrs_irn="NRS-IRN-001",
        nrs_csid="CSID-001",
    )
    db_session.add(filing)
    db_session.commit()

    written = record_filing_facts(
        db_session, filing=filing, user_nin_hash="hash-3", source="filing"
    )
    db_session.commit()
    types = {f.fact_type: f.value for f in written}
    assert types["annual_gross_income"] == "5000000.00"
    assert types["total_tax"] == "690000.00"
    assert types["income_source_count"] == "2"
    assert types["supporting_document_count"] == "1"
    assert types["nrs_irn"] == "NRS-IRN-001"
    assert types["nrs_submission_status"] == "accepted"


def test_record_filing_facts_is_idempotent_per_source(db_session) -> None:
    filing = Filing(
        tax_year=2026,
        return_json=_filing_return(2026, "5000000.00", "690000.00"),
        audit_status="green",
        submission_status="accepted",
    )
    db_session.add(filing)
    db_session.commit()

    first = record_filing_facts(
        db_session, filing=filing, user_nin_hash="h", source="filing"
    )
    db_session.commit()
    second = record_filing_facts(
        db_session, filing=filing, user_nin_hash="h", source="filing"
    )
    db_session.commit()
    assert len(first) > 0
    assert second == []


def test_fact_to_dict_is_json_safe(db_session) -> None:
    row = record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="total_tax",
        value=Decimal("690000.00"),
        label="2026 PIT payable",
    )
    db_session.commit()
    as_dict = fact_to_dict(row)
    assert as_dict["value"] == "690000.00"
    assert as_dict["label"] == "2026 PIT payable"
    assert "recorded_at" in as_dict
