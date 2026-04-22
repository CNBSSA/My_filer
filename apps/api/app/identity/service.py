"""Identity verification service (P5.5).

Orchestrates every NIN check in one place:

1. Refuse if `consent` is not True (NDPR).
2. Hash the NIN for keying.
3. Call the selected aggregator with retry + exponential backoff for the
   24-72h NIN-TIN sync delay referenced in KNOWLEDGE_BASE §10 — transport
   errors (`AggregatorError`) retry up to `max_retries` times; clean
   vendor "not found" responses do NOT retry.
4. On success, vault-encrypt the NIN and upsert the IdentityRecord.
5. Optionally compare the returned full name against a declared name
   (`NameMatchResult`).
6. Append an immutable `ConsentLog` row with the outcome.

The service never writes the raw NIN to its own fields; only the
ciphertext and the HMAC hash land in the DB.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.db.models import ConsentLog, IdentityRecord
from app.identity.base import AggregatorError, IdentityAggregator, NINVerification
from app.identity.name_match import FuzzyResult, fuzzy_match, strict_match
from app.identity.vault import encrypt_nin, hash_nin

log = logging.getLogger("mai_filer.identity")


@dataclass
class VerificationResult:
    """End-to-end outcome returned to callers (Mai tool / endpoint)."""

    verified: bool
    aggregator: str
    nin_hash: str
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    state_of_origin: str | None = None
    name_match: dict | None = None
    name_match_status: str | None = None  # "strict" | "fuzzy" | "mismatch" | None
    error: str | None = None
    attempts: int = 1
    consent_log_id: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "aggregator": self.aggregator,
            "nin_hash": self.nin_hash,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "state_of_origin": self.state_of_origin,
            "name_match": self.name_match,
            "name_match_status": self.name_match_status,
            "error": self.error,
            "attempts": self.attempts,
            "consent_log_id": self.consent_log_id,
        }


class ConsentRequiredError(PermissionError):
    pass


# Backoff schedule for NIN-TIN sync delay per KNOWLEDGE_BASE §10.
DEFAULT_BACKOFF_SECONDS = (2, 4, 8, 16)
MAX_RETRIES = len(DEFAULT_BACKOFF_SECONDS)


class IdentityService:
    def __init__(
        self,
        *,
        aggregator: IdentityAggregator,
        session: Session,
        hash_salt: str,
        vault_key: str,
        backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._aggregator = aggregator
        self._session = session
        self._hash_salt = hash_salt
        self._vault_key = vault_key
        self._backoff = backoff_seconds
        self._sleep = sleep

    def verify_taxpayer(
        self,
        *,
        nin: str,
        consent: bool,
        declared_name: str | None = None,
        purpose: str = "tax_filing",
        user_id: str | None = None,
        thread_id: str | None = None,
    ) -> VerificationResult:
        if not consent:
            raise ConsentRequiredError(
                "Consent is required before querying a NIN (NDPR / NDPC)."
            )
        if not nin.isdigit() or len(nin) != 11:
            raise ValueError("NIN must be exactly 11 digits.")

        nin_hash = hash_nin(nin, salt=self._hash_salt)
        verification, attempts, last_error = self._call_with_retry(nin=nin, consent=consent)

        name_match_status: str | None = None
        name_match: dict | None = None
        if verification and verification.valid and declared_name:
            record_name = verification.canonical_full_name() or ""
            if strict_match(declared_name, record_name):
                name_match_status = "strict"
                name_match = {"ok": True, "mode": "strict"}
            else:
                fuzzy: FuzzyResult = fuzzy_match(declared_name, record_name)
                name_match_status = "fuzzy" if fuzzy.ok else "mismatch"
                name_match = {**fuzzy.as_dict(), "mode": "fuzzy"}

        result = VerificationResult(
            verified=bool(verification and verification.valid),
            aggregator=self._aggregator.name,
            nin_hash=nin_hash,
            attempts=attempts,
            name_match=name_match,
            name_match_status=name_match_status,
            raw=(verification.raw if verification else {}),
            error=last_error,
        )

        if verification and verification.valid:
            result.full_name = verification.canonical_full_name()
            result.first_name = verification.first_name
            result.middle_name = verification.middle_name
            result.last_name = verification.last_name
            result.state_of_origin = verification.state_of_origin
            self._upsert_identity(nin=nin, verification=verification, nin_hash=nin_hash)
        elif verification and verification.error:
            result.error = verification.error

        # Classification:
        #   verified  — we got a valid record back
        #   error     — every retry was a transport failure; no vendor answer
        #   rejected  — vendor answered, but rejected (e.g. NIN not found)
        if result.verified:
            outcome = "verified"
        elif verification is None:
            outcome = "error"
        else:
            outcome = "rejected"

        consent_row = ConsentLog(
            user_id=user_id,
            thread_id=thread_id,
            nin_hash=nin_hash,
            aggregator=self._aggregator.name,
            purpose=purpose,
            consent_granted=consent,
            outcome=outcome,
            name_match_status=name_match_status,
            error_message=result.error,
        )
        self._session.add(consent_row)
        self._session.commit()
        result.consent_log_id = consent_row.id
        return result

    def _call_with_retry(
        self, *, nin: str, consent: bool
    ) -> tuple[NINVerification | None, int, str | None]:
        attempts = 0
        last_error: str | None = None
        verification: NINVerification | None = None

        for attempt_index in range(MAX_RETRIES + 1):
            attempts = attempt_index + 1
            try:
                verification = self._aggregator.verify_nin(nin, consent=consent)
                last_error = verification.error
                return verification, attempts, last_error
            except AggregatorError as exc:
                last_error = str(exc)
                log.warning(
                    "aggregator %s transport error (attempt %d): %s",
                    self._aggregator.name,
                    attempts,
                    exc,
                )
                if attempt_index >= MAX_RETRIES:
                    break
                self._sleep(self._backoff[attempt_index])
        return verification, attempts, last_error

    def _upsert_identity(
        self, *, nin: str, verification: NINVerification, nin_hash: str
    ) -> None:
        ciphertext = encrypt_nin(nin, key=self._vault_key)
        existing = self._session.get(IdentityRecord, nin_hash)
        dob = verification.date_of_birth
        dob_dt = datetime.combine(dob, datetime.min.time()).replace(tzinfo=timezone.utc) if dob else None

        if existing is None:
            record = IdentityRecord(
                nin_hash=nin_hash,
                nin_ciphertext=ciphertext,
                aggregator=verification.aggregator,
                full_name=verification.canonical_full_name(),
                first_name=verification.first_name,
                middle_name=verification.middle_name,
                last_name=verification.last_name,
                date_of_birth=dob_dt,
                gender=verification.gender,
                state_of_origin=verification.state_of_origin,
            )
            self._session.add(record)
        else:
            existing.nin_ciphertext = ciphertext
            existing.aggregator = verification.aggregator
            existing.full_name = verification.canonical_full_name() or existing.full_name
            existing.first_name = verification.first_name or existing.first_name
            existing.middle_name = verification.middle_name or existing.middle_name
            existing.last_name = verification.last_name or existing.last_name
            existing.date_of_birth = dob_dt or existing.date_of_birth
            existing.gender = verification.gender or existing.gender
            existing.state_of_origin = (
                verification.state_of_origin or existing.state_of_origin
            )
