"""SME HTTP surface tests — thin wrappers over Phase 9 calculators."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


def test_calc_cit_endpoint_flags_placeholder() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/sme/calc-cit",
        json={"annual_turnover": 80_000_000, "assessable_profit": 10_000_000},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] in {"small", "medium", "large"}
    assert body["statutory_is_placeholder"] is True
    assert body["cit_amount"] is not None


def test_calc_wht_endpoint_happy_path() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/sme/calc-wht",
        json={"gross_amount": 1_000_000, "transaction_class": "rent"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["wht_amount"] is not None
    assert body["statutory_is_placeholder"] is True


def test_calc_wht_endpoint_unknown_class() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/sme/calc-wht",
        json={"gross_amount": 100, "transaction_class": "invented"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    assert "rent" in body["known_classes"]


def test_list_wht_classes_endpoint() -> None:
    client = TestClient(app)
    r = client.get("/v1/sme/wht-classes")
    assert r.status_code == 200
    assert "rent" in r.json()["classes"]


def test_validate_ubl_endpoint_flags_empty_envelope() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/sme/validate-ubl",
        json={"envelope": {"version": "ubl-3.0", "sections": []}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    codes = {f["code"] for f in body["findings"]}
    assert "UBL-SECTION-COUNT" in codes
