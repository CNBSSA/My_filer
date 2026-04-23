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

from app.db.models import CACRecord, ConsentLog, IdentityRecord
from app.identity.base import (
    AggregatorError,
    CACDirector,
    CACVerification,
    IdentityAggregator,
    NINVerification,
)
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


@dataclass
class CACVerificationResult:
    """End-to-end outcome for a CAC Part-A verification."""

    verified: bool
    aggregator: str
    rc_number: str
    company_name: str | None = None
    company_type: str | None = None
    status: str | None = None
    address: str | None = None
    email: str | None = None
    directors: list[dict] = field(default_factory=list)
    name_match: dict | None = None
    name_match_status: str | None = None
    error: str | None = None
    attempts: int = 1
    consent_log_id: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "verified": self.verified,
            "aggregator": self.aggregator,
            "rc_number": self.rc_number,
            "company_name": self.company_name,
            "company_type": self.company_type,
            "status": self.status,
            "address": self.address,
            "email": self.email,
            "directors": self.directors,
            "name_match": self.name_match,
            "name_match_status": self.name_match_status,
            "error": self.error,
            "attempts": self.attempts,
            "consent_log_id": self.consent_log_id,
        }


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

    # ------------------------------------------------------------------
    # CAC Part-A verification (P9 — corporate filings)
    # ------------------------------------------------------------------

    def verify_organization(
        self,
        *,
        rc_number: str,
        consent: bool,
        declared_name: str | None = None,
        purpose: str = "corporate_filing",
        user_id: str | None = None,
        thread_id: str | None = None,
    ) -> CACVerificationResult:
        """Look up an RC number on the aggregator and persist a CAC snapshot.

        Mirror of `verify_taxpayer` for businesses: consent gate → retry
        loop with the shared backoff schedule → optional name match →
        snapshot upsert → append-only `ConsentLog` row. The RC number is
        normalized (uppercase, trimmed) and used both as the primary key
        on `cac_records` and as the `nin_hash` column on ConsentLog so
        the log stays single-table.
        """
        if not consent:
            raise ConsentRequiredError(
                "Consent is required before querying a CAC record (NDPR / NDPC)."
            )
        cleaned_rc = (rc_number or "").strip().upper()
        if not cleaned_rc or not cleaned_rc.replace("-", "").replace("/", "").isalnum():
            raise ValueError("RC number must be non-empty and alphanumeric.")

        verification, attempts, last_error = self._call_cac_with_retry(
            rc_number=cleaned_rc, consent=consent
        )

        name_match_status: str | None = None
        name_match: dict | None = None
        if verification and verification.valid and declared_name:
            registered = (verification.company_name or "").strip()
            if strict_match(declared_name, registered):
                name_match_status = "strict"
                name_match = {"ok": True, "mode": "strict"}
            else:
                fuzzy: FuzzyResult = fuzzy_match(declared_name, registered)
                name_match_status = "fuzzy" if fuzzy.ok else "mismatch"
                name_match = {**fuzzy.as_dict(), "mode": "fuzzy"}

        directors_payload: list[dict] = []
        if verification and verification.valid:
            directors_payload = [
                {
                    "name": d.name,
                    "role": d.role,
                    "nationality": d.nationality,
                }
                for d in verification.directors
            ]
            self._upsert_cac(verification=verification, directors=verification.directors)

        result = CACVerificationResult(
            verified=bool(verification and verification.valid),
            aggregator=self._aggregator.name,
            rc_number=cleaned_rc,
            company_name=verification.company_name if verification else None,
            company_type=verification.company_type if verification else None,
            status=verification.status if verification else None,
            address=verification.address if verification else None,
            email=verification.email if verification else None,
            directors=directors_payload,
            name_match=name_match,
            name_match_status=name_match_status,
            attempts=attempts,
            raw=(verification.raw if verification else {}),
            error=last_error,
        )

        if verification and verification.valid:
            outcome = "verified"
        elif verification is None:
            outcome = "error"
        else:
            outcome = "rejected"
            if not result.error and verification and verification.error:
                result.error = verification.error

        # Re-use the ConsentLog table: the RC number plays the role of
        # `nin_hash` for CAC queries so one log covers both flows. A
        # dedicated column can be split out later if the volume justifies.
        consent_row = ConsentLog(
            user_id=user_id,
            thread_id=thread_id,
            nin_hash=cleaned_rc,
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

    def _call_cac_with_retry(
        self, *, rc_number: str, consent: bool
    ) -> tuple[CACVerification | None, int, str | None]:
        attempts = 0
        last_error: str | None = None
        verification: CACVerification | None = None

        for attempt_index in range(MAX_RETRIES + 1):
            attempts = attempt_index + 1
            try:
                verification = self._aggregator.verify_cac(rc_number, consent=consent)
                last_error = verification.error
                return verification, attempts, last_error
            except AggregatorError as exc:
                last_error = str(exc)
                log.warning(
                    "aggregator %s CAC transport error (attempt %d): %s",
                    self._aggregator.name,
                    attempts,
                    exc,
                )
                if attempt_index >= MAX_RETRIES:
                    break
                self._sleep(self._backoff[attempt_index])
        return verification, attempts, last_error

    def _upsert_cac(
        self, *, verification: CACVerification, directors: list[CACDirector]
    ) -> None:
        reg = verification.registration_date
        reg_dt = (
            datetime.combine(reg, datetime.min.time()).replace(tzinfo=timezone.utc)
            if reg
            else None
        )
        directors_json = [
            {"name": d.name, "role": d.role, "nationality": d.nationality}
            for d in directors
        ] or None

        existing = self._session.get(CACRecord, verification.rc_number)
        if existing is None:
            self._session.add(
                CACRecord(
                    rc_number=verification.rc_number,
                    aggregator=verification.aggregator,
                    company_name=verification.company_name or "",
                    company_type=verification.company_type,
                    status=verification.status,
                    registration_date=reg_dt,
                    address=verification.address,
                    email=verification.email,
                    directors_json=directors_json,
                )
            )
        else:
            existing.aggregator = verification.aggregator
            existing.company_name = verification.company_name or existing.company_name
            existing.company_type = verification.company_type or existing.company_type
            existing.status = verification.status or existing.status
            existing.registration_date = reg_dt or existing.registration_date
            existing.address = verification.address or existing.address
            existing.email = verification.email or existing.email
            if directors_json:
                existing.directors_json = directors_json
