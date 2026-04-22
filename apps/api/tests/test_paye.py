"""PAYE calculator tests (P2.4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.paye import calculate_paye


def test_no_deductions_matches_pure_pit() -> None:
    """Without any deductions PAYE == PIT on gross."""
    result = calculate_paye(5_000_000)
    # PIT on ₦5m is ₦690,000 per the PIT test suite.
    assert result.annual_tax == Decimal("690000.00")
    assert result.monthly_tax == Decimal("57500.00")
    assert result.chargeable_income == Decimal("5000000.00")
    assert result.deductions.total == Decimal("0.00")


def test_pension_nhis_cra_reduce_chargeable_income() -> None:
    """₦5m gross − ₦400k pension − ₦75k NHIS − ₦1.2m CRA = ₦3.325m chargeable.

      Chargeable = 3,325,000.
      band 1:   800,000 @ 0%   = 0
      band 2: 2,200,000 @ 15%  = 330,000
      band 3:   325,000 @ 18%  = 58,500
      total = 388,500
    """
    result = calculate_paye(
        5_000_000,
        pension=400_000,
        nhis=75_000,
        cra=1_200_000,
    )
    assert result.chargeable_income == Decimal("3325000.00")
    assert result.annual_tax == Decimal("388500.00")
    # 388500 / 12 = 32375 exactly.
    assert result.monthly_tax == Decimal("32375.00")


def test_take_home_is_gross_minus_deductions_minus_tax() -> None:
    result = calculate_paye(
        5_000_000,
        pension=400_000,
        nhis=75_000,
        cra=1_200_000,
    )
    # 5,000,000 - (400,000 + 75,000 + 1,200,000) - 388,500 = 2,936,500
    assert result.take_home_annual == Decimal("2936500.00")
    # Monthly = 244,708.33 (rounded half-up).
    assert result.take_home_monthly == Decimal("244708.33")


def test_deductions_exceed_gross_floors_to_zero_tax() -> None:
    result = calculate_paye(
        500_000,
        pension=200_000,
        nhis=50_000,
        cra=400_000,
    )
    # Chargeable floors at zero; no negative tax.
    assert result.chargeable_income == Decimal("0.00")
    assert result.annual_tax == Decimal("0.00")


def test_negative_inputs_raise() -> None:
    with pytest.raises(ValueError):
        calculate_paye(-1)
    with pytest.raises(ValueError):
        calculate_paye(1_000_000, pension=-10)
    with pytest.raises(ValueError):
        calculate_paye(1_000_000, nhis=-10)
    with pytest.raises(ValueError):
        calculate_paye(1_000_000, cra=-10)
    with pytest.raises(ValueError):
        calculate_paye(1_000_000, other_reliefs=-10)


def test_zero_gross_yields_zero_everywhere() -> None:
    result = calculate_paye(0)
    assert result.annual_tax == Decimal("0.00")
    assert result.monthly_tax == Decimal("0.00")
    assert result.take_home_annual == Decimal("0.00")
    assert result.take_home_monthly == Decimal("0.00")


def test_decimal_input_preserves_precision() -> None:
    result = calculate_paye(
        Decimal("5000000.25"),
        pension=Decimal("400000.10"),
        nhis=Decimal("75000.05"),
        cra=Decimal("1200000.00"),
    )
    expected_chargeable = Decimal("5000000.25") - (
        Decimal("400000.10") + Decimal("75000.05") + Decimal("1200000.00")
    )
    assert result.chargeable_income == expected_chargeable.quantize(Decimal("0.01"))


def test_pit_breakdown_is_available_for_explanation() -> None:
    """Mai Filer's Explanation Engine needs the per-band breakdown."""
    result = calculate_paye(5_000_000, cra=1_000_000)
    # Chargeable = 4,000,000 → bands: 800k@0 + 2.2m@15% + 1m@18% = 330k + 180k = 510k.
    assert result.annual_tax == Decimal("510000.00")
    breakdown = {b.band.order: b for b in result.pit.bands}
    assert breakdown[1].taxable_amount == Decimal("800000")
    assert breakdown[2].taxable_amount == Decimal("2200000")
    assert breakdown[3].taxable_amount == Decimal("1000000")
    assert breakdown[3].tax_amount == Decimal("180000.00")
