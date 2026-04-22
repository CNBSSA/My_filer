"""Corporate Income Tax (CIT) bands — 2026 **PLACEHOLDER**.

The 2026 Nigeria Tax Reform Acts reshaped CIT relative to prior years.
The owner has not yet supplied the confirmed turnover tiers + rates for
this fiscal year, so this module ships illustrative bands so calculators
and tests can run. **Do not ship this file unchanged to production.**

When the owner confirms the 2026 CIT schedule:

  1. Replace `CIT_BANDS_2026` with the authoritative tuple.
  2. Change `CIT_SOURCE` away from `"PLACEHOLDER:..."` — e.g.
     `"NRS circular / 2026-04-01 / CIT Bands v1"`.
  3. Adjust `CIT_TERTIARY_RATE` if the education tax / TETFund rate has
     moved, or delete it entirely if the reform consolidated levies.

`assert_confirmed` in `app/tax/statutory/__init__.py` inspects
`CIT_SOURCE`; any endpoint / Mai tool that touches CIT must call it and
refuse to run while the placeholder is in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CITBand:
    """One turnover tier → CIT rate mapping."""

    tier: str  # "small" | "medium" | "large"
    turnover_max: Decimal | None  # exclusive upper bound; None = no ceiling
    rate: Decimal


# --- PLACEHOLDER VALUES ---------------------------------------------------
# These mirror widely-documented pre-2026 Nigerian CIT tiering; they are
# present so the calculator + tests are meaningful. They are NOT
# authoritative for 2026.
CIT_BANDS_2026: tuple[CITBand, ...] = (
    CITBand(tier="small",  turnover_max=Decimal("25000000"),  rate=Decimal("0.00")),
    CITBand(tier="medium", turnover_max=Decimal("100000000"), rate=Decimal("0.20")),
    CITBand(tier="large",  turnover_max=None,                 rate=Decimal("0.30")),
)

# Tertiary / TETFund education tax on assessable profit. Historically 3%
# applied to Nigerian companies regardless of CIT tier; the 2026 reform
# may have consolidated this into a single levy. Replace / remove on
# owner confirmation.
CIT_TERTIARY_RATE: Decimal = Decimal("0.03")

CIT_SOURCE: str = (
    "PLACEHOLDER: pre-2026 industry-standard tiering; awaiting owner's "
    "confirmed 2026 CIT bands per ADR-0002 / ROADMAP Phase 9"
)


def tier_for_turnover(turnover: Decimal) -> CITBand:
    """Return the CITBand whose `turnover_max` covers `turnover`."""
    for band in CIT_BANDS_2026:
        if band.turnover_max is None or turnover < band.turnover_max:
            return band
    # Should be unreachable — the last band has turnover_max=None.
    return CIT_BANDS_2026[-1]
