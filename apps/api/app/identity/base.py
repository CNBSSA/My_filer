"""Identity aggregator interface (P5.1 + P9 CAC extension).

Mai Filer needs to verify that a NIN belongs to a real person and read back
the NIN holder's identity so the Audit Shield can cross-check the name on
the return. We do **not** call NIMC / CAC directly in v1 — see ADR-0003:
licensed aggregators (Dojah, Seamfix, Prembly) handle the heavy lifting.

For SMEs and corporate filings (Phase 9) we also need CAC Part-A verification
against the Corporate Affairs Commission registry: confirm the RC number
maps to a real business and pull back the registered name + directors.

Each aggregator ships as a small adapter that implements `IdentityAggregator`.
The adapter stays dumb: it receives `(nin, consent)` or `(rc_number, consent)`
+ credentials, calls the vendor, and returns a typed verification. Everything
else (consent log, hashing, name matching, retry/backoff) lives in
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


@dataclass
class CACDirector:
    """One director row pulled from the CAC Part-A register."""

    name: str
    role: str | None = None  # "Director" | "Secretary" | "Shareholder"
    nationality: str | None = None


@dataclass
class CACVerification:
    """Result of a CAC Part-A lookup for an RC number.

    `valid` is True only when the aggregator confirmed the RC number is
    active AND returned at least a company name. Everything beyond that
    (directors, address, status) is best-effort; different aggregators
    surface different slices of the register.
    """

    valid: bool
    aggregator: str
    rc_number: str

    company_name: str | None = None
    company_type: str | None = None  # "LTD" | "PLC" | "BN" | "IT" (NGO) | ...
    registration_date: date | None = None
    status: str | None = None  # "ACTIVE" | "INACTIVE" | "DISSOLVED"
    address: str | None = None
    email: str | None = None
    directors: list[CACDirector] = field(default_factory=list)

    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


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

    def verify_cac(self, rc_number: str, *, consent: bool) -> CACVerification:
        """Look up a CAC RC number against the Corporate Affairs register.

        Implementations MUST:
        - Raise `ValueError` if `rc_number` is empty or not alphanumeric.
        - Raise `PermissionError` if `consent` is not True.
        - Raise `AggregatorError` on transport / 5xx / auth failures.

        Adapters without a CAC integration should raise `AggregatorError`
        with a clear "not wired" message so the service layer can surface
        a 502 instead of pretending the record was verified.
        """
