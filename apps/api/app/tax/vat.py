"""VAT (Value Added Tax) — Nigeria 2026.

Facts from `docs/KNOWLEDGE_BASE.md`:
  - Standard rate: 7.5%
  - Registration / filing threshold: ₦100,000,000 annual turnover

Individual (v1) scope: only `is_vat_registrable()` is typically exercised —
when a PAYE user reports side-business income, Mai Filer checks if they are
approaching or past the threshold. Full VAT payable / input-credit math is
v2 (SME / MBS) territory but the pure calculator lives here for reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

STANDARD_RATE = Decimal("0.075")
REGISTRATION_THRESHOLD = Decimal("100000000")  # ₦100m
TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class VATComputation:
    taxable_supply: Decimal
    exempt_supply: Decimal
    rate: Decimal
    output_vat: Decimal  # VAT collected on supplies
    input_vat: Decimal  # VAT paid on purchases
    net_vat_payable: Decimal  # output - input, floored at 0

    @property
    def total_supply(self) -> Decimal:
        return (self.taxable_supply + self.exempt_supply).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )


def _to_decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_vat(
    taxable_supply: Decimal | int | str,
    *,
    exempt_supply: Decimal | int | str = ZERO,
    input_vat: Decimal | int | str = ZERO,
    rate: Decimal | int | str = STANDARD_RATE,
) -> VATComputation:
    """Compute output VAT, carry input VAT, return net VAT payable.

    - `taxable_supply`: naira value of taxable supplies in the period.
    - `exempt_supply`: naira value of exempt supplies (not VAT-bearing).
    - `input_vat`: VAT already paid on purchases (claimable).
    - `rate`: defaults to 7.5% (the 2026 standard rate).
    """
    taxable = _to_decimal(taxable_supply)
    exempt = _to_decimal(exempt_supply)
    inp_vat = _to_decimal(input_vat)
    r = _to_decimal(rate)

    if taxable < ZERO or exempt < ZERO or inp_vat < ZERO:
        raise ValueError("supply and input VAT must be >= 0")
    if r < ZERO:
        raise ValueError("rate must be >= 0")

    output_vat = _q(taxable * r)
    net = _q(max(ZERO, output_vat - inp_vat))

    return VATComputation(
        taxable_supply=_q(taxable),
        exempt_supply=_q(exempt),
        rate=r,
        output_vat=output_vat,
        input_vat=_q(inp_vat),
        net_vat_payable=net,
    )


def is_vat_registrable(annual_turnover: Decimal | int | str) -> bool:
    """True iff the entity must register for VAT (turnover ≥ ₦100,000,000)."""
    return _to_decimal(annual_turnover) >= REGISTRATION_THRESHOLD


def distance_to_threshold(annual_turnover: Decimal | int | str) -> Decimal:
    """How much more turnover before the user crosses the threshold.

    Negative values mean 'already over'.
    """
    turnover = _to_decimal(annual_turnover)
    return _q(REGISTRATION_THRESHOLD - turnover)
