"""CIT calculator tests (P9.1).

These tests exercise the calculator against injected bands / tertiary
rates. They do NOT assert that the placeholder 2026 rates are authoritative
— that would mislead readers. The confirmed 2026 schedule is still pending
per ADR-0002.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.cit import calculate_cit_2026
from app.tax.statutory.cit_bands import CITBand

THREE_TIER_BANDS = (
    CITBand(tier="small", turnover_max=Decimal("25000000"), rate=Decimal("0.00")),
    CITBand(tier="medium", turnover_max=Decimal("100000000"), rate=Decimal("0.20")),
    CITBand(tier="large", turnover_max=None, rate=Decimal("0.30")),
)


def test_small_company_pays_zero_cit() -> None:
    result = calculate_cit_2026(
        annual_turnover=Decimal("10000000"),
        assessable_profit=Decimal("2000000"),
        bands=THREE_TIER_BANDS,
        tertiary_rate=Decimal("0.03"),
    )
    assert result.tier == "small"
    assert result.cit_amount == Decimal("0.00")
    assert result.tertiary_amount == Decimal("60000.00")
    assert result.total_payable == Decimal("60000.00")


def test_medium_company_20_percent() -> None:
    result = calculate_cit_2026(
        annual_turnover=Decimal("80000000"),
        assessable_profit=Decimal("10000000"),
        bands=THREE_TIER_BANDS,
        tertiary_rate=Decimal("0.03"),
    )
    assert result.tier == "medium"
    assert result.cit_amount == Decimal("2000000.00")
    assert result.tertiary_amount == Decimal("300000.00")
    assert result.total_payable == Decimal("2300000.00")


def test_large_company_30_percent() -> None:
    result = calculate_cit_2026(
        annual_turnover=Decimal("500000000"),
        assessable_profit=Decimal("40000000"),
        bands=THREE_TIER_BANDS,
        tertiary_rate=Decimal("0.03"),
    )
    assert result.tier == "large"
    assert result.cit_amount == Decimal("12000000.00")
    assert result.tertiary_amount == Decimal("1200000.00")
    assert result.total_payable == Decimal("13200000.00")


def test_turnover_exactly_at_band_boundary_falls_into_next_tier() -> None:
    """Upper bound is exclusive — turnover == band.turnover_max lands in next tier."""
    result = calculate_cit_2026(
        annual_turnover=Decimal("25000000"),
        assessable_profit=Decimal("1000000"),
        bands=THREE_TIER_BANDS,
    )
    assert result.tier == "medium"
    assert result.cit_amount == Decimal("200000.00")


def test_tertiary_can_be_disabled() -> None:
    result = calculate_cit_2026(
        annual_turnover=Decimal("80000000"),
        assessable_profit=Decimal("10000000"),
        bands=THREE_TIER_BANDS,
        include_tertiary=False,
    )
    assert result.tertiary_rate == Decimal("0")
    assert result.tertiary_amount == Decimal("0")


def test_negative_inputs_raise() -> None:
    with pytest.raises(ValueError):
        calculate_cit_2026(
            annual_turnover=-1,
            assessable_profit=0,
            bands=THREE_TIER_BANDS,
        )
    with pytest.raises(ValueError):
        calculate_cit_2026(
            annual_turnover=1,
            assessable_profit=Decimal("-1"),
            bands=THREE_TIER_BANDS,
        )


def test_zero_profit_yields_only_zeros() -> None:
    result = calculate_cit_2026(
        annual_turnover=Decimal("50000000"),
        assessable_profit=Decimal("0"),
        bands=THREE_TIER_BANDS,
        tertiary_rate=Decimal("0.03"),
    )
    assert result.cit_amount == Decimal("0.00")
    assert result.tertiary_amount == Decimal("0.00")
    assert result.total_payable == Decimal("0.00")


def test_single_tier_table_unbounded_band() -> None:
    flat = (CITBand(tier="flat", turnover_max=None, rate=Decimal("0.25")),)
    result = calculate_cit_2026(
        annual_turnover=Decimal("1"),
        assessable_profit=Decimal("1000000"),
        bands=flat,
        tertiary_rate=Decimal("0"),
    )
    assert result.tier == "flat"
    assert result.cit_amount == Decimal("250000.00")
