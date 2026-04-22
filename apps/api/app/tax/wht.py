"""Withholding Tax (WHT) calculator — 2026.

Reads rates from `app.tax.statutory.wht_rates`. Each transaction class
maps to a rate; the calculator applies it to the gross payable amount
and returns the WHT to deduct + net payable.

Unknown transaction classes raise `ValueError` rather than silently
falling to a default — WHT is a tax the payer is legally on the hook
for, so guessing is the wrong behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.tax.statutory.wht_rates import WHT_RATES_2026

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class WHTResult:
    transaction_class: str
    gross_amount: Decimal
    wht_rate: Decimal
    wht_amount: Decimal
    net_payable: Decimal


def _to_decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def known_transaction_classes(
    rates: dict[str, Decimal] | None = None,
) -> list[str]:
    return sorted((rates or WHT_RATES_2026).keys())


def calculate_wht(
    *,
    gross_amount: Decimal | int | str,
    transaction_class: str,
    rates: dict[str, Decimal] | None = None,
) -> WHTResult:
    """Return the WHT amount + net payable for a transaction.

    Callers may inject a `rates` dict for testing / forecasting. When
    omitted, the current statutory table is used.
    """
    gross = _to_decimal(gross_amount)
    if gross < ZERO:
        raise ValueError("gross_amount must be >= 0")

    active_rates = rates if rates is not None else WHT_RATES_2026
    if transaction_class not in active_rates:
        raise ValueError(
            f"unknown transaction_class '{transaction_class}'. "
            f"Known classes: {sorted(active_rates)}"
        )
    rate = active_rates[transaction_class]

    wht_amount = _q(gross * rate)
    net = _q(gross - wht_amount)

    return WHTResult(
        transaction_class=transaction_class,
        gross_amount=_q(gross),
        wht_rate=rate,
        wht_amount=wht_amount,
        net_payable=net,
    )
