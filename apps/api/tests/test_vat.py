"""VAT calculator tests (P2.11)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.vat import (
    REGISTRATION_THRESHOLD,
    STANDARD_RATE,
    calculate_vat,
    distance_to_threshold,
    is_vat_registrable,
)


def test_standard_rate_is_seven_and_a_half_percent() -> None:
    assert STANDARD_RATE == Decimal("0.075")


def test_registration_threshold_is_one_hundred_million() -> None:
    assert REGISTRATION_THRESHOLD == Decimal("100000000")


def test_is_vat_registrable_boundaries() -> None:
    assert is_vat_registrable(99_999_999) is False
    assert is_vat_registrable(100_000_000) is True
    assert is_vat_registrable(500_000_000) is True
    assert is_vat_registrable(0) is False


def test_distance_to_threshold_positive_and_negative() -> None:
    assert distance_to_threshold(0) == Decimal("100000000.00")
    assert distance_to_threshold(80_000_000) == Decimal("20000000.00")
    assert distance_to_threshold(150_000_000) == Decimal("-50000000.00")


def test_calculate_vat_on_pure_taxable_supply() -> None:
    result = calculate_vat(1_000_000)
    assert result.output_vat == Decimal("75000.00")
    assert result.input_vat == Decimal("0.00")
    assert result.net_vat_payable == Decimal("75000.00")
    assert result.total_supply == Decimal("1000000.00")


def test_input_vat_credit_reduces_payable() -> None:
    result = calculate_vat(2_000_000, input_vat=50_000)
    # 150,000 - 50,000 = 100,000.
    assert result.output_vat == Decimal("150000.00")
    assert result.net_vat_payable == Decimal("100000.00")


def test_input_vat_exceeding_output_floors_payable_to_zero() -> None:
    result = calculate_vat(100_000, input_vat=20_000)
    # 7,500 - 20,000 < 0 → 0.
    assert result.output_vat == Decimal("7500.00")
    assert result.net_vat_payable == Decimal("0.00")


def test_exempt_supply_does_not_attract_vat() -> None:
    result = calculate_vat(1_000_000, exempt_supply=500_000)
    assert result.output_vat == Decimal("75000.00")
    assert result.total_supply == Decimal("1500000.00")


def test_custom_rate_is_honored() -> None:
    result = calculate_vat(1_000_000, rate=Decimal("0.1"))
    assert result.output_vat == Decimal("100000.00")


def test_negative_inputs_raise() -> None:
    with pytest.raises(ValueError):
        calculate_vat(-1)
    with pytest.raises(ValueError):
        calculate_vat(1_000, exempt_supply=-1)
    with pytest.raises(ValueError):
        calculate_vat(1_000, input_vat=-1)
    with pytest.raises(ValueError):
        calculate_vat(1_000, rate=-Decimal("0.01"))
