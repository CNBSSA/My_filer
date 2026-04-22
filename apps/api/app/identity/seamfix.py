"""Seamfix NIN verification adapter (P5.3 — stub).

Seamfix ships a direct NIMC-licensed KYC API. We keep this as a shell so a
production cutover from Dojah to Seamfix is a one-env-var swap, not a
rewrite. The adapter signs requests with an API key header; swapping to
HMAC / JWT (if Seamfix updates their auth) is a local change here.

Wire up the real request/response shape when we have sandbox credentials
from the owner (ADR-0003 notes Seamfix as the primary alternate; it is
not exercised in CI smoke tests yet).
"""

from __future__ import annotations

from app.identity.base import AggregatorError, NINVerification


class SeamfixAdapter:
    name = "seamfix"

    def __init__(self, *, api_key: str, base_url: str = "https://api.seamfix.com/v1") -> None:
        if not api_key:
            raise ValueError("SeamfixAdapter requires an api_key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def verify_nin(self, nin: str, *, consent: bool) -> NINVerification:
        if not nin.isdigit() or len(nin) != 11:
            raise ValueError("NIN must be exactly 11 digits")
        if not consent:
            raise PermissionError(
                "consent=True is mandatory before any NIN query (NDPR / NDPC)"
            )
        raise AggregatorError(
            "Seamfix adapter not wired to a live endpoint yet (awaiting sandbox creds)"
        )
