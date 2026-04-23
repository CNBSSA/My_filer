"""Memory HTTP endpoint tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.memory.facts import record_fact

pytestmark = pytest.mark.usefixtures("override_db")


def test_get_facts_returns_stored_rows(db_session) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="annual_gross_income",
        value=Decimal("5000000"),
    )
    db_session.commit()
    client = TestClient(app)
    resp = client.get("/v1/memory/facts", params={"nin_hash": "h"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["facts"]) == 1
    assert body["facts"][0]["fact_type"] == "annual_gross_income"


def test_recall_endpoint_returns_matching_facts(db_session) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="total_tax",
        value=Decimal("690000"),
        label="2026 PIT",
    )
    db_session.commit()
    client = TestClient(app)
    resp = client.get(
        "/v1/memory/recall", params={"q": "PIT", "nin_hash": "h"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["facts"]) == 1
    assert body["facts"][0]["label"] == "2026 PIT"


def test_anomalies_endpoint(db_session) -> None:
    for year, value in [(2025, Decimal("5000000")), (2026, Decimal("10000000"))]:
        record_fact(
            db_session,
            user_nin_hash="h",
            tax_year=year,
            fact_type="annual_gross_income",
            value=value,
        )
    db_session.commit()
    client = TestClient(app)
    resp = client.get(
        "/v1/memory/anomalies",
        params={"current_year": 2026, "nin_hash": "h"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["findings"]) == 1
    assert body["findings"][0]["severity"] == "alert"


def test_nudges_endpoint_flags_band_cross(db_session) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="annual_gross_income",
        value=Decimal("2500000"),
    )
    db_session.commit()
    client = TestClient(app)
    resp = client.get(
        "/v1/memory/nudges",
        params={
            "current_year": 2026,
            "ytd_gross": "2500000",
            "month": 3,
            "nin_hash": "h",
        },
    )
    assert resp.status_code == 200
    codes = {n["code"] for n in resp.json()["nudges"]}
    assert "PIT_BAND_CROSS" in codes
