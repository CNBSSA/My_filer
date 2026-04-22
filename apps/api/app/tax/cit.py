"""Corporate Income Tax (CIT) calculator — 2026.

Consumes the injectable band table from `app.tax.statutory.cit_bands`
so real 2026 rates drop in as a single-file replacement. The calculator
itself never hard-codes a tier or rate.

Scope: determines the CIT tier from annual turnover, applies the tier's
rate to assessable profit, optionally adds the tertiary-education-tax
component if the current statutory table still carries it. Separate
levies (Police Trust Fund, NITDA) are not modelled here — they move
into their own calculators if / when the owner confirms they still
apply post-reform.

This module is callable with the placeholder statutory data (for tests
and local dev). Endpoints and Mai's tool layer gate on
`assert_confirmed(CIT_SOURCE, label='cit_bands')` before they run in
production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.tax.statutory.cit_bands import (
    CIT_BANDS_2026,
    CIT_TERTIARY_RATE,
    CITBand,
    tier_for_turnover,
)

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class CITResult:
    annual_turnover: Decimal
    assessable_profit: Decimal
    tier: str
    cit_rate: Decimal
    cit_amount: Decimal
    tertiary_rate: Decimal
    tertiary_amount: Decimal
    total_payable: Decimal
    notes: list[str] = field(default_factory=list)


def _to_decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _non_negative(name: str, value: Decimal) -> Decimal:
    if value < ZERO:
        raise ValueError(f"{name} must be >= 0")
    return value


def calculate_cit_2026(
    *,
    annual_turnover: Decimal | int | str,
    assessable_profit: Decimal | int | str,
    include_tertiary: bool = True,
    bands: tuple[CITBand, ...] | None = None,
    tertiary_rate: Decimal | None = None,
) -> CITResult:
    """Compute CIT + tertiary tax on a Nigerian company's return.

    Callers pass `annual_turnover` (determines tier) and
    `assessable_profit` (the base for CIT). Both are in naira.

    Band + tertiary rates default to the currently-configured statutory
    tables; injecting them makes the function fully testable without
    patching the module.
    """
    turnover = _non_negative("annual_turnover", _to_decimal(annual_turnover))
    profit = _non_negative("assessable_profit", _to_decimal(assessable_profit))

    active_bands = bands or CIT_BANDS_2026
    active_tertiary_rate = (
        tertiary_rate if tertiary_rate is not None else CIT_TERTIARY_RATE
    )

    # Resolve tier (mirrors statutory.cit_bands.tier_for_turnover but
    # respects injected bands).
    tier: CITBand | None = None
    for band in active_bands:
        if band.turnover_max is None or turnover < band.turnover_max:
            tier = band
            break
    if tier is None:
        tier = active_bands[-1]

    cit_amount = _q(profit * tier.rate)

    tertiary_amount = ZERO
    if include_tertiary and active_tertiary_rate > 0:
        tertiary_amount = _q(profit * active_tertiary_rate)

    total = _q(cit_amount + tertiary_amount)

    notes: list[str] = []
    if tier.rate == 0:
        notes.append(
            f"Tier '{tier.tier}' currently maps to 0% CIT; no CIT payable on this return."
        )
    if tier_for_turnover(turnover).tier != tier.tier:
        notes.append(
            "Injected bands produced a different tier than the currently-installed "
            "statutory table — verify caller intent."
        )

    return CITResult(
        annual_turnover=_q(turnover),
        assessable_profit=_q(profit),
        tier=tier.tier,
        cit_rate=tier.rate,
        cit_amount=cit_amount,
        tertiary_rate=active_tertiary_rate if include_tertiary else ZERO,
        tertiary_amount=tertiary_amount,
        total_payable=total,
        notes=notes,
    )
