"""Personal Income Tax (PIT) — 2026 bands.

Source of truth: `docs/KNOWLEDGE_BASE.md §3`.

    Band 1: ₦0            – ₦800,000       0%
    Band 2: Next ₦2,200,000                15%
    Band 3: Next ₦9,000,000                18%
    Band 4: Next ₦13,000,000               21%
    Band 5: Next ₦25,000,000               23%
    Band 6: Above ₦50,000,000              25%

Pure function, deterministic, tested. Consumed by:
- `apps/api/app/tax/paye.py` (after deductions)
- `apps/api/app/agents/mai_filer/tools.py` as a Claude tool
- the Audit Shield for recomputation checks

Arithmetic uses `Decimal` to avoid floating-point drift on naira/kobo amounts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class PITBand:
    """One slice of the progressive PIT schedule."""

    order: int
    name: str
    lower: Decimal  # inclusive lower bound of the band (on gross income)
    width: Decimal | None  # None means "unbounded top band"
    rate: Decimal

    @property
    def upper(self) -> Decimal | None:
        """Exclusive upper bound, or None if this is the top band."""
        if self.width is None:
            return None
        return self.lower + self.width


# The 2026 bands. Ordered, with exact widths so we never guess.
PIT_BANDS_2026: tuple[PITBand, ...] = (
    PITBand(1, "Exempt band",        Decimal("0"),           Decimal("800000"),    Decimal("0.00")),
    PITBand(2, "Lower band",         Decimal("800000"),      Decimal("2200000"),   Decimal("0.15")),
    PITBand(3, "Middle band",        Decimal("3000000"),     Decimal("9000000"),   Decimal("0.18")),
    PITBand(4, "Upper-middle band",  Decimal("12000000"),    Decimal("13000000"),  Decimal("0.21")),
    PITBand(5, "Upper band",         Decimal("25000000"),    Decimal("25000000"),  Decimal("0.23")),
    PITBand(6, "Top band",           Decimal("50000000"),    None,                 Decimal("0.25")),
)


@dataclass(frozen=True)
class PITBandBreakdown:
    """How much of `annual_income` fell in this band and the tax it yielded."""

    band: PITBand
    taxable_amount: Decimal
    tax_amount: Decimal


@dataclass(frozen=True)
class PITResult:
    annual_income: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    bands: list[PITBandBreakdown] = field(default_factory=list)

    @property
    def take_home(self) -> Decimal:
        return (self.annual_income - self.total_tax).quantize(TWO_PLACES, ROUND_HALF_UP)


def _to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_naira(amount: Decimal) -> Decimal:
    """Round to kobo (2dp) with banker-safe half-up."""
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_pit_2026(annual_income: Decimal | int | str) -> PITResult:
    """Apply the 2026 PIT bands progressively to `annual_income`.

    Negative income raises ValueError; callers that mean "no income this
    year" should pass `0`.
    """
    income = _to_decimal(annual_income)
    if income < ZERO:
        raise ValueError("annual_income must be >= 0")

    remaining = income
    total_tax = ZERO
    breakdowns: list[PITBandBreakdown] = []

    for band in PIT_BANDS_2026:
        if remaining <= ZERO:
            breakdowns.append(PITBandBreakdown(band=band, taxable_amount=ZERO, tax_amount=ZERO))
            continue

        if band.width is None:
            taxable = remaining
        else:
            taxable = min(remaining, band.width)

        tax = _quantize_naira(taxable * band.rate)
        total_tax += tax
        remaining -= taxable

        breakdowns.append(
            PITBandBreakdown(band=band, taxable_amount=taxable, tax_amount=tax)
        )

    total_tax = _quantize_naira(total_tax)

    if income > ZERO:
        effective = (total_tax / income).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        effective = Decimal("0.0000")

    return PITResult(
        annual_income=_quantize_naira(income),
        total_tax=total_tax,
        effective_rate=effective,
        bands=breakdowns,
    )
