"""WHT calculator tests (P9.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.wht import calculate_wht, known_transaction_classes

FAKE_RATES = {
    "rent": Decimal("0.10"),
    "consulting": Decimal("0.05"),
}


def test_known_classes_includes_standard_ones() -> None:
    classes = known_transaction_classes()
    for c in ["rent", "professional_services", "dividend", "interest"]:
        assert c in classes


def test_calculate_wht_on_rent() -> None:
    result = calculate_wht(
        gross_amount=Decimal("1000000"),
        transaction_class="rent",
        rates=FAKE_RATES,
    )
    assert result.wht_amount == Decimal("100000.00")
    assert result.net_payable == Decimal("900000.00")
    assert result.wht_rate == Decimal("0.10")


def test_calculate_wht_on_consulting() -> None:
    result = calculate_wht(
        gross_amount=Decimal("500000"),
        transaction_class="consulting",
        rates=FAKE_RATES,
    )
    assert result.wht_amount == Decimal("25000.00")
    assert result.net_payable == Decimal("475000.00")


def test_unknown_class_raises() -> None:
    with pytest.raises(ValueError) as exc:
        calculate_wht(
            gross_amount=Decimal("100"),
            transaction_class="invented_class",
            rates=FAKE_RATES,
        )
    assert "invented_class" in str(exc.value)


def test_negative_gross_raises() -> None:
    with pytest.raises(ValueError):
        calculate_wht(
            gross_amount=Decimal("-1"),
            transaction_class="rent",
            rates=FAKE_RATES,
        )


def test_zero_gross_yields_zero_wht() -> None:
    result = calculate_wht(
        gross_amount=Decimal("0"),
        transaction_class="rent",
        rates=FAKE_RATES,
    )
    assert result.wht_amount == Decimal("0.00")
    assert result.net_payable == Decimal("0.00")


def test_default_rates_table_is_injected_when_none_given() -> None:
    """Without an explicit `rates` param the statutory table is used."""
    result = calculate_wht(
        gross_amount=Decimal("1000000"),
        transaction_class="rent",
    )
    # Placeholder rate for rent is 10% in the current table.
    assert result.wht_rate > 0
    assert result.wht_amount > 0
