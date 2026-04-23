"""NGO / tax-exempt body rules — 2026 **PLACEHOLDER**.

Mai Filer's Phase 11 (NGO track) needs to know:

  * what purposes qualify an organization for tax-exempt status under
    Nigerian law in 2026,
  * what returns / schedules NGOs must still file even when exempt from
    CIT,
  * when WHT must be withheld + remitted on payments an NGO makes,
  * how CAC Part-C registration numbers are structured so identity
    validation doesn't false-reject them.

None of this is yet confirmed by the owner. The constants below are
illustrative scaffolding so the calculators, schemas, and tests run.
The `*_SOURCE` strings are prefixed `PLACEHOLDER:` so the
`assert_confirmed` guard refuses production use until real values land.

When the owner supplies the confirmed NRS NGO specification:

  1. Replace the four constants below.
  2. Change every `NGO_*_SOURCE` away from `"PLACEHOLDER:..."`.
  3. If NRS published a schedule for WHT remittance by NGOs, fold it
     into `NGO_WHT_REMITTANCE` keyed by the transaction class from
     `app/tax/statutory/wht_rates.py`.
"""

from __future__ import annotations

from decimal import Decimal


# ---------------------------------------------------------------------------
# Exemption classification
# ---------------------------------------------------------------------------

# The set of organizational purposes NRS recognises as exemption-eligible.
# Replace with the authoritative enum once confirmed.
NGO_EXEMPT_PURPOSES: tuple[str, ...] = (
    "charitable",
    "educational",
    "religious",
    "scientific",
    "cultural",
    "social_welfare",
)


# CAC Part-C (incorporated trustees) RC numbers. The exact NRS-recognised
# pattern is NOT yet confirmed; the placeholder below rejects obvious
# garbage without pretending to be authoritative.
NGO_CAC_PART_C_PATTERN: str = r"^(IT|CAC\/IT)[-/]?\d{4,8}$"


# ---------------------------------------------------------------------------
# WHT-remittance obligations placeholder
# ---------------------------------------------------------------------------

# NGOs are typically exempt from CIT but must still withhold and remit
# tax on payments they make (salaries, rent, professional services, etc.).
# This map says "when NGO pays for this, WHT still applies at this rate".
#
# PLACEHOLDER — mirrors the pre-2026 convention that NGO WHT rates
# match the general schedule in `wht_rates.py`. Replace only if NRS
# documents NGO-specific deviations (e.g. a charity-discount rate).
NGO_WHT_REMITTANCE: dict[str, Decimal] = {
    "rent": Decimal("0.10"),
    "professional_services": Decimal("0.10"),
    "construction": Decimal("0.05"),
    "salary": Decimal("0.00"),  # payroll handled via PAYE, not WHT
    "other": Decimal("0.05"),
}


# ---------------------------------------------------------------------------
# Annual filing window placeholder
# ---------------------------------------------------------------------------

# Months after the fiscal year-end within which an exempt body must
# file its annual return. Replace when the NRS cycle is confirmed.
NGO_FILING_WINDOW_MONTHS: int = 6


# ---------------------------------------------------------------------------
# Source markers used by assert_confirmed
# ---------------------------------------------------------------------------

NGO_RULES_SOURCE: str = (
    "PLACEHOLDER: illustrative NGO exemption + CAC Part-C pattern + WHT "
    "remittance schedule; awaiting owner's confirmed 2026 NRS NGO "
    "specification per ROADMAP Phase 11"
)


def known_exempt_purposes() -> list[str]:
    return list(NGO_EXEMPT_PURPOSES)
