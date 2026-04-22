"""Filing endpoint tests (P4.4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.filings import get_storage as filings_get_storage
from app.db.models import Filing
from app.documents.storage import InMemoryStorage
from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


def _payload(*, declaration: bool = True, tax_year: int = 2026) -> dict[str, Any]:
    return PITReturn(
        tax_year=tax_year,
        period_start=date(tax_year, 1, 1),
        period_end=date(tax_year, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
            residential_address="1 Ikoyi Crescent, Lagos",
        ),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(tax_year, 1, 1),
                period_end=date(tax_year, 12, 31),
            )
        ],
        declaration=declaration,
    ).model_dump(mode="json")


def _override_storage() -> InMemoryStorage:
    storage = InMemoryStorage()
    app.dependency_overrides[filings_get_storage] = lambda: storage
    return storage


def test_create_and_read_filing(db_session) -> None:
    try:
        client = TestClient(app)
        created = client.post("/v1/filings", json=_payload())
        assert created.status_code == 201
        filing_id = created.json()["id"]
        assert created.json()["audit_status"] == "pending"

        fetched = client.get(f"/v1/filings/{filing_id}")
        assert fetched.status_code == 200
        assert fetched.json()["tax_year"] == 2026

        stored = db_session.get(Filing, filing_id)
        assert stored is not None
        assert stored.return_json["tax_year"] == 2026
    finally:
        app.dependency_overrides.clear()


def test_audit_flips_status_to_green_for_valid_return() -> None:
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/filings", json=_payload()).json()["id"]
        audit = client.post(f"/v1/filings/{filing_id}/audit")
        assert audit.status_code == 200
        body = audit.json()
        assert body["audit"]["status"] == "green"
        assert body["filing"]["audit_status"] == "green"
    finally:
        app.dependency_overrides.clear()


def test_audit_is_red_when_declaration_not_affirmed() -> None:
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/filings", json=_payload(declaration=False)).json()["id"]
        audit = client.post(f"/v1/filings/{filing_id}/audit")
        assert audit.json()["audit"]["status"] == "red"
        codes = {f["code"] for f in audit.json()["audit"]["findings"]}
        assert "DECLARATION_NOT_AFFIRMED" in codes
    finally:
        app.dependency_overrides.clear()


def test_pack_build_and_download_green_path() -> None:
    storage = _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/filings", json=_payload()).json()["id"]
        build = client.post(f"/v1/filings/{filing_id}/pack")
        assert build.status_code == 200
        pack = build.json()["pack"]
        assert pack["settlement"]["direction"] == "payable"
        assert build.json()["filing"]["pack_ready"] is True

        pdf_resp = client.get(f"/v1/filings/{filing_id}/pack.pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"].startswith("application/pdf")
        assert pdf_resp.content.startswith(b"%PDF")

        json_resp = client.get(f"/v1/filings/{filing_id}/pack.json")
        assert json_resp.status_code == 200
        # JSON pack must echo the settlement block.
        import json
        body = json.loads(json_resp.content)
        assert body["tax_year"] == 2026
        assert body["settlement"]["direction"] == "payable"

        # Storage adapter actually received both blobs.
        assert len(storage._blobs) == 2  # type: ignore[attr-defined]
    finally:
        app.dependency_overrides.clear()


def test_pack_build_refused_when_audit_red() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post(
            "/v1/filings", json=_payload(declaration=False)
        ).json()["id"]
        resp = client.post(f"/v1/filings/{filing_id}/pack")
        assert resp.status_code == 409
        assert "red" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_update_resets_audit_and_pack_state() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/filings", json=_payload()).json()["id"]
        client.post(f"/v1/filings/{filing_id}/pack")  # finalize
        updated = _payload()
        updated["notes"] = "added a note"
        put = client.put(f"/v1/filings/{filing_id}", json=updated)
        assert put.status_code == 200
        body = put.json()
        assert body["audit_status"] == "pending"
        assert body["pack_ready"] is False
    finally:
        app.dependency_overrides.clear()
