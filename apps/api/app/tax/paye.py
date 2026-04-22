"""PAYE — Pay-As-You-Earn for individual employment income.

PAYE is PIT applied to *chargeable income* — that is, annual gross
employment income less statutory deductions:

    chargeable = gross
                 - pension contribution
                 - NHIS contribution
                 - Consolidated Relief Allowance (CRA)
                 - any other allowable reliefs (life insurance, NHF, ...)

This module stays explicit about its inputs. The CRA formula in force for
the 2026 reform year is not yet documented in our Knowledge Base — callers
pass CRA in directly (so the agent can profile the user and compute it, or
so the test harness can assert an exact number). The same is true for
pension, NHIS, and any other reliefs.

The function returns a `PAYEResult` that carries the PIT breakdown so
Mai Filer can explain the math band-by-band (Role 5 — Explanation Engine).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.tax.pit import PITResult, TWO_PLACES, calculate_pit_2026

ZERO = Decimal("0")


@dataclass(frozen=True)
class PAYEDeductions:
    pension: Decimal = ZERO
    nhis: Decimal = ZERO
    cra: Decimal = ZERO
    other_reliefs: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return (self.pension + self.nhis + self.cra + self.other_reliefs).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class PAYEResult:
    annual_gross: Decimal
    deductions: PAYEDeductions
    chargeable_income: Decimal
    pit: PITResult

    @property
    def annual_tax(self) -> Decimal:
        return self.pit.total_tax

    @property
    def monthly_tax(self) -> Decimal:
        return (self.annual_tax / Decimal(12)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @property
    def take_home_annual(self) -> Decimal:
        return (self.annual_gross - self.deductions.total - self.annual_tax).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

    @property
    def take_home_monthly(self) -> Decimal:
        return (self.take_home_annual / Decimal(12)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )


def _to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _non_negative(name: str, value: Decimal) -> Decimal:
    if value < ZERO:
        raise ValueError(f"{name} must be >= 0")
    return value


def calculate_paye(
    annual_gross: Decimal | int | str,
    *,
    pension: Decimal | int | str = ZERO,
    nhis: Decimal | int | str = ZERO,
    cra: Decimal | int | str = ZERO,
    other_reliefs: Decimal | int | str = ZERO,
) -> PAYEResult:
    """Compute annual + monthly PAYE on employment income.

    All amounts are annual figures in naira. Negative inputs raise; zero is
    fine. If total deductions exceed gross, chargeable income floors at 0
    (no negative tax).
    """
    gross = _non_negative("annual_gross", _to_decimal(annual_gross))
    deductions = PAYEDeductions(
        pension=_non_negative("pension", _to_decimal(pension)),
        nhis=_non_negative("nhis", _to_decimal(nhis)),
        cra=_non_negative("cra", _to_decimal(cra)),
        other_reliefs=_non_negative("other_reliefs", _to_decimal(other_reliefs)),
    )

    chargeable = max(ZERO, gross - deductions.total)
    pit = calculate_pit_2026(chargeable)

    return PAYEResult(
        annual_gross=gross.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        deductions=deductions,
        chargeable_income=chargeable.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        pit=pit,
    )
