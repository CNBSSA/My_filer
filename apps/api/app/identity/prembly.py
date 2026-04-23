"""Prembly NIN verification adapter (P5.4 — stub).

Prembly (formerly Blusalt) exposes a multi-country KYC API. Same adapter
pattern as Dojah — ADR-0003 lists it as our second alternate. The real
request shape lands when we activate their sandbox.
"""

from __future__ import annotations

from app.identity.base import AggregatorError, CACVerification, NINVerification


class PremblyAdapter:
    name = "prembly"

    def __init__(self, *, api_key: str, base_url: str = "https://api.prembly.com/v1") -> None:
        if not api_key:
            raise ValueError("PremblyAdapter requires an api_key")
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
            "Prembly adapter not wired to a live endpoint yet (awaiting sandbox creds)"
        )

    def verify_cac(self, rc_number: str, *, consent: bool) -> CACVerification:
        cleaned = (rc_number or "").strip().upper()
        if not cleaned or not cleaned.replace("-", "").replace("/", "").isalnum():
            raise ValueError("RC number must be non-empty and alphanumeric")
        if not consent:
            raise PermissionError(
                "consent=True is mandatory before any CAC query (NDPR / NDPC)"
            )
        raise AggregatorError(
            "Prembly CAC adapter not wired to a live endpoint yet (awaiting sandbox creds)"
        )
