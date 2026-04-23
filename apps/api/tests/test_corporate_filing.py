"""Corporate (CIT) filing tests — schema, serializer, audit, service,
endpoint, Mai tools (Phase 9)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.corporate_filings import get_storage as corp_get_storage
from app.db.models import Filing
from app.documents.storage import InMemoryStorage
from app.filing.corporate_audit import audit as audit_corporate
from app.filing.corporate_schemas import (
    CITReturn,
    CorporateTaxpayer,
    ExpenseLine,
    RevenueLine,
)
from app.filing.corporate_serialize import (
    build_canonical_pack,
    compute_return_totals,
)
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


def _return(
    *,
    declaration: bool = True,
    revenues: list[tuple[str, str]] | None = None,
    expenses: list[tuple[str, str, str]] | None = None,
    declared_turnover: str | None = None,
    supporting_docs: list[str] | None = None,
) -> CITReturn:
    return CITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=CorporateTaxpayer(
            rc_number="RC-123456",
            company_name="Globacom Limited",
            company_type="LTD",
            tin="12345678-0001",
            industry="telecoms",
            registered_address="1 Mike Adenuga Way, Lagos",
        ),
        revenues=[
            RevenueLine(label=label, amount=Decimal(amt))
            for label, amt in (revenues or [("Airtime sales", "60000000")])
        ],
        expenses=[
            ExpenseLine(kind=kind, label=label, amount=Decimal(amt))
            for kind, label, amt in (
                expenses
                or [
                    ("cost_of_sales", "Carrier interconnect", "20000000"),
                    ("salaries_wages", "Staff costs", "8000000"),
                ]
            )
        ],
        declared_turnover=(Decimal(declared_turnover) if declared_turnover else None),
        declaration=declaration,
        supporting_document_ids=supporting_docs or [],
    )


def _payload(**kwargs) -> dict[str, Any]:
    return _return(**kwargs).model_dump(mode="json")


def _override_storage() -> InMemoryStorage:
    storage = InMemoryStorage()
    app.dependency_overrides[corp_get_storage] = lambda: storage
    return storage


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_schema_rejects_negative_revenue() -> None:
    with pytest.raises(Exception):
        RevenueLine(label="X", amount=Decimal("-1"))


def test_schema_rejects_bad_officer_nin() -> None:
    with pytest.raises(Exception):
        CorporateTaxpayer(
            rc_number="RC-1",
            company_name="C",
            primary_officer_nin="123",  # not 11 digits
        )


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def test_compute_totals_fills_aggregates() -> None:
    result = compute_return_totals(_return())
    assert result.total_revenue == Decimal("60000000.00")
    assert result.total_expenses == Decimal("28000000.00")
    assert result.computation is not None
    assert result.computation.assessable_profit == Decimal("32000000.00")
    # Medium tier on pre-2026 placeholder bands: 20% CIT + 3% tertiary.
    assert result.computation.cit_rate == Decimal("0.20")
    assert result.computation.cit_amount == Decimal("6400000.00")
    assert result.computation.tertiary_amount == Decimal("960000.00")
    assert result.computation.total_payable == Decimal("7360000.00")


def test_canonical_pack_redacts_officer_nin() -> None:
    ret = _return()
    ret.taxpayer.primary_officer_nin = "12345678901"
    ret.taxpayer.primary_officer_name = "Chidi Okafor"
    pack = build_canonical_pack(ret)
    assert pack["taxpayer"]["primary_officer_nin"] == "[REDACTED]"
    assert pack["taxpayer"]["primary_officer_name"] == "Chidi Okafor"


def test_canonical_pack_carries_statutory_source_banner() -> None:
    pack = build_canonical_pack(_return())
    assert pack["statutory_source"].startswith("PLACEHOLDER")


def test_net_payable_absorbs_wht_and_advance_tax() -> None:
    ret = _return()
    ret.wht_already_suffered = Decimal("1000000")
    ret.advance_tax_paid = Decimal("500000")
    result = compute_return_totals(ret)
    # total_payable 7,360,000 - 1,500,000 = 5,860,000
    assert result.net_payable == Decimal("5860000.00")


def test_loss_clamps_cit_base_to_zero() -> None:
    ret = _return(
        revenues=[("Airtime sales", "1000000")],
        expenses=[("cost_of_sales", "Carrier interconnect", "3000000")],
    )
    result = compute_return_totals(ret)
    # Assessable profit is negative, but CIT is computed on 0.
    assert result.computation is not None
    assert result.computation.assessable_profit == Decimal("-2000000.00")
    assert result.computation.cit_amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# Audit Shield
# ---------------------------------------------------------------------------


def test_audit_green_with_valid_return_warns_on_placeholder() -> None:
    report = audit_corporate(_return(supporting_docs=["doc-1"]))
    # Placeholder CIT bands always emits a warning, so status is yellow.
    assert report.status == "yellow"
    codes = {f.code for f in report.findings}
    assert "CIT_RATES_PLACEHOLDER" in codes


def test_audit_red_when_declaration_not_affirmed() -> None:
    report = audit_corporate(_return(declaration=False))
    assert report.status == "red"
    assert any(f.code == "CIT_DECLARATION_NOT_AFFIRMED" for f in report.findings)


def test_audit_red_when_no_revenue_and_no_declared_turnover() -> None:
    ret = _return(revenues=[])
    ret.revenues = []
    ret.declared_turnover = None
    report = audit_corporate(ret)
    assert report.status == "red"
    assert any(f.code == "CIT_NO_REVENUE" for f in report.findings)


def test_audit_flags_turnover_mismatch() -> None:
    ret = _return(declared_turnover="1000000")
    # Revenues sum to 60,000,000 — far above declared turnover.
    report = audit_corporate(ret)
    codes = {f.code for f in report.findings}
    assert "CIT_TURNOVER_MISMATCH" in codes


def test_audit_heavy_loss_warns() -> None:
    ret = _return(
        revenues=[("Airtime sales", "1000000")],
        expenses=[("cost_of_sales", "C", "10000000")],
    )
    report = audit_corporate(ret)
    assert any(f.code == "CIT_HEAVY_LOSS" for f in report.findings)


# ---------------------------------------------------------------------------
# Service + endpoints
# ---------------------------------------------------------------------------


def test_create_and_read_corporate_filing() -> None:
    try:
        client = TestClient(app)
        created = client.post("/v1/corporate-filings", json=_payload())
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["tax_kind"] == "cit"
        assert body["audit_status"] == "pending"
        filing_id = body["id"]

        fetched = client.get(f"/v1/corporate-filings/{filing_id}")
        assert fetched.status_code == 200
        assert fetched.json()["tax_year"] == 2026
    finally:
        app.dependency_overrides.clear()


def test_audit_endpoint_yellow_for_valid_return() -> None:
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/corporate-filings", json=_payload()).json()["id"]
        resp = client.post(f"/v1/corporate-filings/{filing_id}/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["audit"]["status"] == "yellow"  # placeholder banner
        assert body["filing"]["audit_status"] == "yellow"
    finally:
        app.dependency_overrides.clear()


def test_pack_build_and_download_yellow_allowed() -> None:
    """The placeholder banner is only a warning — packs still generate."""
    storage = _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/corporate-filings", json=_payload()).json()["id"]
        build = client.post(f"/v1/corporate-filings/{filing_id}/pack")
        assert build.status_code == 200, build.text
        pack = build.json()["pack"]
        assert pack["pack_version"] == "mai-filer-cit-v1"
        assert pack["taxpayer"]["rc_number"] == "RC-123456"

        pdf = client.get(f"/v1/corporate-filings/{filing_id}/pack.pdf")
        assert pdf.status_code == 200
        assert pdf.content.startswith(b"%PDF")
        assert pdf.headers["content-type"].startswith("application/pdf")

        json_resp = client.get(f"/v1/corporate-filings/{filing_id}/pack.json")
        assert json_resp.status_code == 200
        body = json.loads(json_resp.content)
        assert body["computation"]["tier"] in {"small", "medium", "large"}

        assert len(storage._blobs) == 2  # type: ignore[attr-defined]
    finally:
        app.dependency_overrides.clear()


def test_pack_refused_when_audit_red() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post(
            "/v1/corporate-filings", json=_payload(declaration=False)
        ).json()["id"]
        resp = client.post(f"/v1/corporate-filings/{filing_id}/pack")
        assert resp.status_code == 409
        assert "red" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_put_resets_audit_and_pack_state() -> None:
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = client.post("/v1/corporate-filings", json=_payload()).json()["id"]
        client.post(f"/v1/corporate-filings/{filing_id}/pack")

        updated = _payload()
        updated["notes"] = "revised"
        put = client.put(f"/v1/corporate-filings/{filing_id}", json=updated)
        assert put.status_code == 200
        body = put.json()
        assert body["audit_status"] == "pending"
        assert body["pack_ready"] is False
    finally:
        app.dependency_overrides.clear()


def test_endpoint_rejects_wrong_tax_kind(db_session) -> None:
    """PUT against a CIT route on a PIT filing should 400."""
    pit_filing = Filing(
        tax_year=2026,
        tax_kind="pit",
        return_json={},
        audit_status="pending",
    )
    db_session.add(pit_filing)
    db_session.commit()
    try:
        client = TestClient(app)
        resp = client.get(f"/v1/corporate-filings/{pit_filing.id}")
        assert resp.status_code == 400
        assert "tax_kind" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mai tools
# ---------------------------------------------------------------------------


def test_mai_tool_audit_corporate_return() -> None:
    from app.agents.mai_filer.tools import run_tool

    payload = _payload()
    raw = run_tool("audit_corporate_return", {"return_": payload})
    body = json.loads(raw)
    assert body["status"] in {"green", "yellow", "red"}
    assert body["statutory_is_placeholder"] is True


def test_mai_tool_audit_corporate_filing_rejects_wrong_kind(db_session) -> None:
    from app.agents.mai_filer.tools import run_tool

    pit_filing = Filing(
        tax_year=2026, tax_kind="pit", return_json={}, audit_status="pending"
    )
    db_session.add(pit_filing)
    db_session.commit()

    raw = run_tool("audit_corporate_filing", {"filing_id": pit_filing.id})
    body = json.loads(raw)
    assert body["reason"] == "tax_kind_mismatch"


def test_mai_tool_audit_corporate_filing_happy_path() -> None:
    from app.agents.mai_filer.tools import run_tool

    try:
        client = TestClient(app)
        filing_id = client.post("/v1/corporate-filings", json=_payload()).json()["id"]

        raw = run_tool("audit_corporate_filing", {"filing_id": filing_id})
        body = json.loads(raw)
        assert body["status"] == "yellow"
        assert body["tax_kind"] == "cit"
        assert body["statutory_is_placeholder"] is True
    finally:
        app.dependency_overrides.clear()
