"""Withholding Tax (WHT) rates — 2026 **PLACEHOLDER**.

Each transaction class carries its own WHT rate. The 2026 reform may
have consolidated or adjusted classes — owner has not confirmed.

When the owner supplies the 2026 matrix:

  1. Replace `WHT_RATES_2026` with the authoritative map.
  2. Change `WHT_SOURCE` away from `"PLACEHOLDER:..."`.
  3. If NRS adds new classes, extend the `WHTClass` literal in
     `app/tax/wht.py` to match.
"""

from __future__ import annotations

from decimal import Decimal

# --- PLACEHOLDER VALUES ---------------------------------------------------
# These mirror commonly cited pre-2026 WHT rates for Nigerian companies.
# They are NOT authoritative for 2026.
WHT_RATES_2026: dict[str, Decimal] = {
    "rent": Decimal("0.10"),
    "professional_services": Decimal("0.10"),
    "construction": Decimal("0.05"),
    "commission": Decimal("0.05"),
    "dividend": Decimal("0.10"),
    "interest": Decimal("0.10"),
    "royalty": Decimal("0.10"),
    "technical_services": Decimal("0.10"),
    "management_services": Decimal("0.10"),
    "directors_fee": Decimal("0.10"),
    "contract_of_supply": Decimal("0.05"),
    "other": Decimal("0.05"),
}


WHT_SOURCE: str = (
    "PLACEHOLDER: pre-2026 industry-standard WHT rates; awaiting owner's "
    "confirmed 2026 WHT schedule per ADR-0002 / ROADMAP Phase 9"
)
