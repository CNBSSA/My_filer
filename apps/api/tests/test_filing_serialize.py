"""Canonical pack builder tests (P4.2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity
from app.filing.serialize import build_canonical_pack, compute_return_totals


def _base_return() -> PITReturn:
    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
            residential_address="1 Ikoyi Crescent, Lagos",
            email="chidi@example.com",
        ),
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


def test_compute_return_totals_populates_computation_and_totals() -> None:
    computed = compute_return_totals(_base_return())
    assert computed.computation is not None
    # PIT on ₦5m with zero deductions is ₦690,000 per Phase 2 tests.
    assert computed.computation.total_tax == Decimal("690000.00")
    assert computed.total_gross_income == Decimal("5000000.00")
    # net_payable = annual_tax - paye_already_withheld (which is pulled from
    # per-source tax_withheld when not declared explicitly).
    assert computed.paye_already_withheld == Decimal("650000.00")
    assert computed.net_payable == Decimal("40000.00")


def test_canonical_pack_has_stable_top_level_keys() -> None:
    pack = build_canonical_pack(_base_return())
    assert pack["pack_version"] == "mai-filer-pit-v1"
    for key in (
        "tax_year",
        "period",
        "taxpayer",
        "income",
        "deductions",
        "computation",
        "settlement",
        "declaration",
    ):
        assert key in pack, f"missing key {key}"


def test_canonical_pack_renders_amounts_as_strings() -> None:
    pack = build_canonical_pack(_base_return())
    assert pack["income"]["total_gross"] == "5000000.00"
    assert pack["computation"]["total_tax"] == "690000.00"
    assert pack["settlement"]["net_payable"] == "40000.00"
    assert pack["settlement"]["direction"] == "payable"


def test_settlement_direction_for_refund() -> None:
    """When withheld exceeds liability, direction is 'refund'."""
    ret = _base_return()
    ret.income_sources[0].tax_withheld = Decimal("800000")  # more than 690k owed
    pack = build_canonical_pack(ret)
    assert pack["settlement"]["direction"] == "refund"
    assert pack["settlement"]["net_payable"] == "-110000.00"


def test_income_sources_serialize_in_order() -> None:
    ret = _base_return()
    ret.income_sources.append(
        IncomeSource(
            kind="rental",
            payer_name="Shonibare Estates",
            gross_amount=Decimal("1200000"),
            tax_withheld=Decimal("0"),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
        )
    )
    pack = build_canonical_pack(ret)
    assert [s["kind"] for s in pack["income"]["sources"]] == ["employment", "rental"]
    assert pack["income"]["total_gross"] == "6200000.00"
