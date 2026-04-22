"""Identity aggregator interface (P5.1).

Mai Filer needs to verify that a NIN belongs to a real person and read back
the NIN holder's identity so the Audit Shield can cross-check the name on
the return. We do **not** call NIMC directly in v1 — see ADR-0003:
licensed aggregators (Dojah, Seamfix, Prembly) handle the heavy lifting.

Each aggregator ships as a small adapter that implements `IdentityAggregator`.
The adapter stays dumb: it receives `(nin, consent)` + credentials, calls
the vendor, and returns a `NINVerification`. Everything else (consent log,
NIN hashing, vault write, name matching, retry/backoff) lives in
`identity/service.py` so the rules stay in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


@dataclass
class NINVerification:
    """Result of a NIN verification round-trip.

    `valid` is True only when the aggregator confirmed the NIN belongs to a
    real record AND we got back enough identity to match. If the NIN is
    format-valid but the vendor could not find it, `valid=False` and
    `error` carries the vendor's reason.
    """

    valid: bool
    aggregator: str
    nin: str

    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    state_of_origin: str | None = None
    phone: str | None = None

    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def canonical_full_name(self) -> str | None:
        """Return the cleanest full name we can assemble."""
        if self.full_name:
            return self.full_name.strip()
        parts = [p for p in (self.first_name, self.middle_name, self.last_name) if p]
        return " ".join(parts).strip() or None


class AggregatorError(RuntimeError):
    """Raised by adapters for transport / auth / upstream failures."""


class IdentityAggregator(Protocol):
    """Stable surface every adapter implements."""

    name: str

    def verify_nin(self, nin: str, *, consent: bool) -> NINVerification:
        """Look up a NIN on the vendor and return a `NINVerification`.

        Implementations MUST:
        - Raise `ValueError` if `nin` is not 11 digits.
        - Raise `PermissionError` if `consent` is not True (NDPR rule).
        - Raise `AggregatorError` on transport / 5xx / auth failures so the
          service can decide whether to retry with the next vendor.
        """
