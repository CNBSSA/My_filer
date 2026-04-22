"""Statutory tables — the numbers that change by fiscal year.

Every rate, band, threshold, or field list that can be updated by an NRS
circular lives here. The rest of the codebase imports from this package
and never hard-codes a rate. When the owner supplies confirmed 2026
figures, the update is a single-file replacement — no logic changes.

Each table ships with a `SOURCE` constant that records where the numbers
came from (or that they are placeholders pending owner confirmation).
Production code refuses to use placeholder tables unless the caller has
explicitly opted in; see `assert_confirmed()`.
"""

from __future__ import annotations

from app.tax.statutory.cit_bands import (
    CIT_BANDS_2026,
    CIT_SOURCE,
    CIT_TERTIARY_RATE,
    CITBand,
)
from app.tax.statutory.wht_rates import (
    WHT_RATES_2026,
    WHT_SOURCE,
)
from app.tax.statutory.ubl_fields import (
    UBL_REQUIRED_FIELDS_2026,
    UBL_SECTIONS,
    UBL_SOURCE,
)


class PlaceholderStatutoryError(RuntimeError):
    """Raised when production code tries to read placeholder data."""


def is_placeholder(source: str) -> bool:
    """True iff the loaded table is flagged as PLACEHOLDER pending owner input."""
    return source.startswith("PLACEHOLDER")


def assert_confirmed(source: str, *, label: str) -> None:
    """Guard used by endpoints / services that must not ship on placeholders."""
    if is_placeholder(source):
        raise PlaceholderStatutoryError(
            f"{label} statutory table is a placeholder. "
            f"Replace `apps/api/app/tax/statutory/{label}.py` with confirmed "
            f"2026 values before using this surface in production."
        )


__all__ = [
    "CITBand",
    "CIT_BANDS_2026",
    "CIT_SOURCE",
    "CIT_TERTIARY_RATE",
    "PlaceholderStatutoryError",
    "UBL_REQUIRED_FIELDS_2026",
    "UBL_SECTIONS",
    "UBL_SOURCE",
    "WHT_RATES_2026",
    "WHT_SOURCE",
    "assert_confirmed",
    "is_placeholder",
]
