"""NGO Audit Shield tests (P11.4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.filing.ngo_audit import audit
from app.filing.ngo_schemas import (
    NGOExpenditureBlock,
    NGOIncomeBlock,
    NGOReturn,
    Organization,
    WHTScheduleRow,
)


def _green() -> NGOReturn:
    return NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-200345",
            legal_name="Sample Exempt Body",
            purpose="charitable",
        ),
        income=NGOIncomeBlock(local_donations=Decimal("5000000")),
        expenditure=NGOExpenditureBlock(
            program_expenses=Decimal("4000000"),
            administrative=Decimal("500000"),
        ),
        wht_schedule=[
            WHTScheduleRow(
                period_month=5,
                transaction_class="rent",
                recipient_category="corporate",
                gross_amount=Decimal("1000000"),
                wht_amount=Decimal("100000"),
            ),
        ],
        supporting_document_ids=["doc-1"],
        exemption_status_declaration=True,
        declaration=True,
    )


def test_green_path_on_complete_affirmed_return() -> None:
    report = audit(_green(), today=date(2026, 6, 30))
    assert report.status == "green"
    assert report.findings == []


def test_red_when_cac_part_c_rc_does_not_match_pattern() -> None:
    r = _green()
    r.organization.cac_part_c_rc = "random-string"
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_IDENTITY_CAC_INVALID" in {f.code for f in report.findings}


def test_red_when_tax_year_is_in_future() -> None:
    r = _green()
    r.tax_year = 2030
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_TAX_YEAR_IN_FUTURE" in {f.code for f in report.findings}


def test_red_when_exemption_status_not_affirmed() -> None:
    r = _green()
    r.exemption_status_declaration = False
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_EXEMPTION_NOT_AFFIRMED" in {f.code for f in report.findings}


def test_red_when_declaration_not_affirmed() -> None:
    r = _green()
    r.declaration = False
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_DECLARATION_NOT_AFFIRMED" in {f.code for f in report.findings}


def test_red_when_wht_amount_exceeds_gross_on_row() -> None:
    r = _green()
    r.wht_schedule[0].wht_amount = Decimal("2000000")  # > gross 1m
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    codes = {f.code for f in report.findings}
    assert "NGO_WHT_EXCEEDS_GROSS" in codes


def test_red_on_empty_return() -> None:
    r = NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-111", legal_name="Empty Body", purpose="charitable"
        ),
        exemption_status_declaration=True,
        declaration=True,
    )
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_EMPTY_RETURN" in {f.code for f in report.findings}


def test_yellow_when_purpose_is_other() -> None:
    r = _green()
    r.organization.purpose = "other"
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "yellow"
    assert "NGO_PURPOSE_OTHER" in {f.code for f in report.findings}


def test_yellow_when_program_expenses_without_supporting_docs() -> None:
    r = _green()
    r.supporting_document_ids = []
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "yellow"
    assert "NGO_SUPPORTING_DOCS_MISSING" in {f.code for f in report.findings}


def test_name_required() -> None:
    r = _green()
    r.organization.legal_name = " "
    report = audit(r, today=date(2026, 6, 30))
    assert report.status == "red"
    assert "NGO_IDENTITY_NAME_MISSING" in {f.code for f in report.findings}
