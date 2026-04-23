"""NGO canonical pack tests (P11.2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.filing.ngo_schemas import (
    NGOExpenditureBlock,
    NGOIncomeBlock,
    NGOReturn,
    Organization,
    WHTScheduleRow,
)
from app.filing.ngo_serialize import build_canonical_pack, compute_return_totals


def _sample_return() -> NGOReturn:
    return NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-100234",
            legal_name="Mai Filer Community Trust",
            purpose="charitable",
            registered_address="4 Kofo Abayomi, Victoria Island",
            email="trustees@mai-filer-ct.org",
        ),
        income=NGOIncomeBlock(
            local_donations=Decimal("5000000"),
            foreign_donations=Decimal("12000000"),
            government_grants=Decimal("3000000"),
            foundation_grants=Decimal("8000000"),
            program_income=Decimal("2000000"),
        ),
        expenditure=NGOExpenditureBlock(
            program_expenses=Decimal("22000000"),
            administrative=Decimal("3000000"),
            fundraising=Decimal("2000000"),
        ),
        wht_schedule=[
            WHTScheduleRow(
                period_month=3,
                transaction_class="professional_services",
                recipient_category="corporate",
                gross_amount=Decimal("1000000"),
                wht_amount=Decimal("100000"),
            ),
            WHTScheduleRow(
                period_month=9,
                transaction_class="rent",
                recipient_category="individual",
                gross_amount=Decimal("2000000"),
                wht_amount=Decimal("200000"),
            ),
        ],
        exemption_status_declaration=True,
        declaration=True,
    )


def test_compute_return_totals_sums_income_expenditure_wht() -> None:
    r = compute_return_totals(_sample_return())
    assert r.total_income == Decimal("30000000.00")
    assert r.total_expenditure == Decimal("27000000.00")
    assert r.total_wht_remitted == Decimal("300000.00")
    assert r.net_result == Decimal("3000000.00")


def test_canonical_pack_top_level_keys() -> None:
    pack = build_canonical_pack(_sample_return())
    for key in (
        "pack_version",
        "tax_year",
        "period",
        "organization",
        "income",
        "expenditure",
        "wht_schedule",
        "summary",
        "exemption_status_declaration",
        "declaration",
    ):
        assert key in pack
    assert pack["pack_version"] == "mai-filer-ngo-v1"


def test_canonical_pack_renders_amounts_as_strings() -> None:
    pack = build_canonical_pack(_sample_return())
    assert pack["summary"]["total_income"] == "30000000.00"
    assert pack["summary"]["total_expenditure"] == "27000000.00"
    assert pack["summary"]["total_wht_remitted"] == "300000.00"
    assert pack["summary"]["net_result"] == "3000000.00"
    assert pack["summary"]["direction"] == "surplus"


def test_direction_deficit_when_expenditure_exceeds_income() -> None:
    r = _sample_return()
    r.expenditure.program_expenses = Decimal("40000000")  # now expenditure > income
    pack = build_canonical_pack(r)
    assert pack["summary"]["direction"] == "deficit"


def test_direction_balanced_when_equal() -> None:
    r = NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-99999", legal_name="Balanced Trust", purpose="charitable"
        ),
        income=NGOIncomeBlock(local_donations=Decimal("1000000")),
        expenditure=NGOExpenditureBlock(program_expenses=Decimal("1000000")),
        exemption_status_declaration=True,
        declaration=True,
    )
    pack = build_canonical_pack(r)
    assert pack["summary"]["direction"] == "balanced"


def test_wht_schedule_rows_serialize_in_order() -> None:
    pack = build_canonical_pack(_sample_return())
    rows = pack["wht_schedule"]
    assert [r["period_month"] for r in rows] == [3, 9]
    assert rows[0]["wht_amount"] == "100000.00"
