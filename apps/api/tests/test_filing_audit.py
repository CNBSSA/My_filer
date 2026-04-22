"""Audit Shield tests (P4.6)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.filing.audit import audit
from app.filing.schemas import (
    Deductions,
    IncomeSource,
    PITReturn,
    TaxpayerIdentity,
)


def _minimal_return() -> PITReturn:
    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(nin="12345678901", full_name="Chidi Okafor"),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
        ],
        declaration=True,
    )


def test_green_when_return_is_complete_and_affirmed() -> None:
    report = audit(_minimal_return(), today=date(2026, 5, 1))
    assert report.status == "green"
    assert report.findings == []


def test_red_when_declaration_is_missing() -> None:
    ret = _minimal_return()
    ret.declaration = False
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "DECLARATION_NOT_AFFIRMED" in codes


def test_red_when_no_income_sources() -> None:
    ret = _minimal_return()
    ret.income_sources = []
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "NO_INCOME_SOURCES" in codes


def test_red_when_withheld_exceeds_gross_on_source() -> None:
    ret = _minimal_return()
    ret.income_sources[0].tax_withheld = Decimal("6000000")
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "INCOME_WITHHELD_EXCEEDS_GROSS" in codes


def test_red_when_tax_year_is_in_future() -> None:
    ret = _minimal_return()
    ret.tax_year = 2030
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "TAX_YEAR_IN_FUTURE" in codes


def test_red_when_total_deductions_exceed_gross() -> None:
    ret = _minimal_return()
    ret.deductions = Deductions(
        pension=Decimal("3000000"),
        nhis=Decimal("3000000"),
    )
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "DEDUCTIONS_EXCEED_GROSS" in codes


def test_yellow_when_pension_unusually_high() -> None:
    ret = _minimal_return()
    # Just above 50% but under gross → warning, not error.
    ret.deductions = Deductions(pension=Decimal("2600000"))
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "yellow"
    codes = {f.code for f in report.findings}
    assert "PENSION_EXCEEDS_HALF_GROSS" in codes


def test_yellow_when_withheld_totals_mismatch() -> None:
    ret = _minimal_return()
    ret.paye_already_withheld = Decimal("999999")
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "yellow"
    codes = {f.code for f in report.findings}
    assert "WITHHELD_MISMATCH" in codes


def test_yellow_when_income_source_refers_to_missing_supporting_doc() -> None:
    ret = _minimal_return()
    ret.income_sources[0].supporting_document_id = "doc-xyz"
    # Not added to supporting_document_ids on the return.
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "yellow"
    codes = {f.code for f in report.findings}
    assert "SUPPORTING_DOC_NOT_ATTACHED" in codes


def test_red_when_nin_invalid() -> None:
    ret = _minimal_return()
    # Bypass Pydantic by assigning after construction — simulate bad upstream input.
    ret.taxpayer = ret.taxpayer.model_copy()
    object.__setattr__(ret.taxpayer, "nin", "abc123")
    report = audit(ret, today=date(2026, 5, 1))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "IDENTITY_NIN_INVALID" in codes
