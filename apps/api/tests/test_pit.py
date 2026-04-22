"""PIT 2026 calculator tests (P2.2).

Bands per `docs/KNOWLEDGE_BASE.md §3`:
  0%   on first ₦800,000
  15%  on next ₦2,200,000     (up to ₦3m)
  18%  on next ₦9,000,000     (up to ₦12m)
  21%  on next ₦13,000,000    (up to ₦25m)
  23%  on next ₦25,000,000    (up to ₦50m)
  25%  above ₦50,000,000

All assertions use exact decimal comparisons, not approximate floats.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.pit import PIT_BANDS_2026, calculate_pit_2026


def test_zero_income_yields_zero_tax() -> None:
    result = calculate_pit_2026(0)
    assert result.total_tax == Decimal("0.00")
    assert result.effective_rate == Decimal("0.0000")
    assert result.take_home == Decimal("0.00")
    assert len(result.bands) == len(PIT_BANDS_2026)
    for band in result.bands:
        assert band.taxable_amount == Decimal("0")
        assert band.tax_amount == Decimal("0")


def test_negative_income_raises() -> None:
    with pytest.raises(ValueError):
        calculate_pit_2026(-1)


def test_exempt_band_exact_threshold() -> None:
    """₦800,000 sits exactly inside band 1 → 0 tax."""
    result = calculate_pit_2026(800_000)
    assert result.total_tax == Decimal("0.00")
    assert result.bands[0].taxable_amount == Decimal("800000")
    assert result.bands[1].taxable_amount == Decimal("0")


def test_income_within_second_band() -> None:
    """₦2,000,000 → 0 on first 800k + 15% on next 1.2m = ₦180,000."""
    result = calculate_pit_2026(2_000_000)
    assert result.total_tax == Decimal("180000.00")
    assert result.bands[1].taxable_amount == Decimal("1200000")
    assert result.bands[1].tax_amount == Decimal("180000.00")


def test_five_million_maps_to_expected_bands() -> None:
    """₦5,000,000:
      band 1: 800,000 @ 0%     = 0
      band 2: 2,200,000 @ 15%  = 330,000
      band 3: 2,000,000 @ 18%  = 360,000
      total = 690,000
    """
    result = calculate_pit_2026(5_000_000)
    assert result.total_tax == Decimal("690000.00")
    assert result.bands[0].taxable_amount == Decimal("800000")
    assert result.bands[1].taxable_amount == Decimal("2200000")
    assert result.bands[2].taxable_amount == Decimal("2000000")
    # Bands 4-6 receive nothing.
    for band in result.bands[3:]:
        assert band.taxable_amount == Decimal("0")


def test_twelve_million_tops_out_band_three() -> None:
    """₦12,000,000 fills bands 1-3 exactly:
      band 1: 800,000 @ 0%     = 0
      band 2: 2,200,000 @ 15%  = 330,000
      band 3: 9,000,000 @ 18%  = 1,620,000
      total = 1,950,000
    """
    result = calculate_pit_2026(12_000_000)
    assert result.total_tax == Decimal("1950000.00")
    assert result.bands[3].taxable_amount == Decimal("0")


def test_twenty_five_million_tops_out_band_four() -> None:
    """₦25,000,000 fills bands 1-4:
      band 1: 800,000     @ 0%   = 0
      band 2: 2,200,000   @ 15%  = 330,000
      band 3: 9,000,000   @ 18%  = 1,620,000
      band 4: 13,000,000  @ 21%  = 2,730,000
      total = 4,680,000
    """
    result = calculate_pit_2026(25_000_000)
    assert result.total_tax == Decimal("4680000.00")
    assert result.bands[4].taxable_amount == Decimal("0")


def test_fifty_million_tops_out_band_five() -> None:
    """₦50,000,000 fills bands 1-5:
      1: 0  + 2: 330,000 + 3: 1,620,000 + 4: 2,730,000
      5: 25,000,000 @ 23% = 5,750,000
      total = 10,430,000
    """
    result = calculate_pit_2026(50_000_000)
    assert result.total_tax == Decimal("10430000.00")
    assert result.bands[5].taxable_amount == Decimal("0")


def test_sixty_million_enters_top_band() -> None:
    """₦60,000,000 = ₦50m to bands 1-5 (₦10,430,000 tax) + ₦10m @ 25% (₦2,500,000 tax)."""
    result = calculate_pit_2026(60_000_000)
    assert result.bands[5].taxable_amount == Decimal("10000000")
    assert result.bands[5].tax_amount == Decimal("2500000.00")
    assert result.total_tax == Decimal("12930000.00")


def test_effective_rate_is_reported() -> None:
    result = calculate_pit_2026(5_000_000)
    # ₦690,000 / ₦5,000,000 = 0.138 exactly → 0.1380 at 4dp.
    assert result.effective_rate == Decimal("0.1380")


def test_decimal_input_with_kobo_is_handled() -> None:
    result = calculate_pit_2026(Decimal("2000000.50"))
    # Same bands as 2,000,000 plus 0.50 at 15% = 0.075 → rounds kobo-precise.
    # Band 2 taxable = 1,200,000.50; 15% of that = 180,000.075 → 180000.08.
    assert result.bands[1].tax_amount == Decimal("180000.08")
    # Total equals band 2 tax here (bands 3+ receive nothing).
    assert result.total_tax == Decimal("180000.08")


def test_bands_are_ordered_and_cover_the_schedule() -> None:
    assert [band.order for band in PIT_BANDS_2026] == [1, 2, 3, 4, 5, 6]
    expected_rates = [
        Decimal("0.00"),
        Decimal("0.15"),
        Decimal("0.18"),
        Decimal("0.21"),
        Decimal("0.23"),
        Decimal("0.25"),
    ]
    assert [band.rate for band in PIT_BANDS_2026] == expected_rates
