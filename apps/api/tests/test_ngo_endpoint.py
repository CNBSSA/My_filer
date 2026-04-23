"""NGO filing endpoint tests (P11.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.ngo_filings import get_storage as ngo_get_storage
from app.db.models import Filing
from app.documents.storage import InMemoryStorage
from app.filing.ngo_schemas import (
    NGOExpenditureBlock,
    NGOIncomeBlock,
    NGOReturn,
    Organization,
    WHTScheduleRow,
)
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


def _payload(*, declaration: bool = True, exemption: bool = True) -> dict[str, Any]:
    return NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-123456",
            legal_name="Test Exempt Trust",
            purpose="charitable",
        ),
        income=NGOIncomeBlock(local_donations=Decimal("5000000")),
        expenditure=NGOExpenditureBlock(program_expenses=Decimal("4000000")),
        wht_schedule=[
            WHTScheduleRow(
                period_month=1,
                transaction_class="rent",
                recipient_category="corporate",
                gross_amount=Decimal("1000000"),
                wht_amount=Decimal("100000"),
            )
        ],
        supporting_document_ids=["doc-xyz"],
        exemption_status_declaration=exemption,
        declaration=declaration,
    ).model_dump(mode="json")


def _override_storage() -> InMemoryStorage:
    storage = InMemoryStorage()
    app.dependency_overrides[ngo_get_storage] = lambda: storage
    return storage


def test_create_and_read_ngo_filing(db_session) -> None:
    try:
        client = TestClient(app)
        created = client.post("/v1/ngo-filings", json=_payload())
        assert created.status_code == 201
        body = created.json()
        assert body["tax_kind"] == "ngo_annual"
        assert body["audit_status"] == "pending"

        row = db_session.get(Filing, body["id"])
        assert row is not None
        assert row.tax_kind == "ngo_annual"
    finally:
        app.dependency_overrides.clear()


def test_ngo_endpoints_reject_non_ngo_filing(db_session) -> None:
    """A PIT filing must not answer to the NGO routes."""
    filing = Filing(
        tax_year=2026, tax_kind="pit", return_json={}, audit_status="green"
    )
    db_session.add(filing)
    db_session.commit()
    try:
        client = TestClient(app)
        resp = client.get(f"/v1/ngo-filings/{filing.id}")
        assert resp.status_code == 400
        assert "tax_kind" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_audit_flips_status_to_green() -> None:
    try:
        client = TestClient(app)
        fid = client.post("/v1/ngo-filings", json=_payload()).json()["id"]
        audit = client.post(f"/v1/ngo-filings/{fid}/audit")
        assert audit.status_code == 200
        body = audit.json()
        assert body["audit"]["status"] == "green"
        assert body["filing"]["audit_status"] == "green"
    finally:
        app.dependency_overrides.clear()


def test_audit_red_when_declarations_missing() -> None:
    try:
        client = TestClient(app)
        fid = client.post(
            "/v1/ngo-filings", json=_payload(declaration=False, exemption=False)
        ).json()["id"]
        body = client.post(f"/v1/ngo-filings/{fid}/audit").json()
        assert body["audit"]["status"] == "red"
        codes = {f["code"] for f in body["audit"]["findings"]}
        assert "NGO_DECLARATION_NOT_AFFIRMED" in codes
        assert "NGO_EXEMPTION_NOT_AFFIRMED" in codes
    finally:
        app.dependency_overrides.clear()


def test_pack_build_and_download_green_path() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        fid = client.post("/v1/ngo-filings", json=_payload()).json()["id"]
        build = client.post(f"/v1/ngo-filings/{fid}/pack")
        assert build.status_code == 200, build.text
        pack = build.json()["pack"]
        assert pack["pack_version"] == "mai-filer-ngo-v1"
        assert pack["summary"]["total_income"] == "5000000.00"

        pdf = client.get(f"/v1/ngo-filings/{fid}/pack.pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")

        json_pack = client.get(f"/v1/ngo-filings/{fid}/pack.json")
        assert json_pack.status_code == 200
        import json as _json

        body = _json.loads(json_pack.content)
        assert body["organization"]["cac_part_c_rc"] == "IT-123456"
    finally:
        app.dependency_overrides.clear()


def test_pack_refused_on_red_audit() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        fid = client.post(
            "/v1/ngo-filings", json=_payload(declaration=False)
        ).json()["id"]
        resp = client.post(f"/v1/ngo-filings/{fid}/pack")
        assert resp.status_code == 409
        assert "red" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
