"""Gateway service — orchestrates NRS submission for a finalized filing.

The service:

1. Reloads the canonical pack (Phase 4 already persisted JSON + PDF).
2. If NRS credentials are configured → call the signed gateway.
3. If credentials are missing → run a **simulated** submission so local
   dev / preview environments can still exercise the end-to-end path.
   Simulated submissions generate deterministic IRN / CSID / QR values
   so the UI can render them without pretending they came from NRS.
4. Persists the outcome onto the `Filing` row: irn / csid / qr, status,
   submission_error, submitted_at.
5. Re-raises configuration issues as `SubmissionConfigError` so the
   endpoint returns a clean 400/409 rather than leaking stack traces.

Retry + backoff happen inside `NRSClient.submit_filing`; this layer
only sees the terminal outcome.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Filing
from app.filing.schemas import PITReturn
from app.filing.serialize import build_canonical_pack
from app.gateway.client import (
    NRSAuthError,
    NRSClient,
    NRSRejection,
    NRSResponse,
    NRSTransportError,
    build_default_nrs_client,
)
from app.gateway.errors import translate_error

log = logging.getLogger("mai_filer.gateway.service")


class SubmissionConfigError(RuntimeError):
    """Raised when the filing itself isn't ready to submit (not audited / red)."""


@dataclass
class SubmissionOutcome:
    """Return shape for callers (endpoint, Mai tool)."""

    filing_id: str
    status: str  # "accepted" | "rejected" | "simulated" | "error"
    irn: str | None = None
    csid: str | None = None
    qr_payload: str | None = None
    error: dict[str, str] | None = None  # translated from NRS code
    simulated: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filing_id": self.filing_id,
            "status": self.status,
            "irn": self.irn,
            "csid": self.csid,
            "qr_payload": self.qr_payload,
            "error": self.error,
            "simulated": self.simulated,
        }


def submit_filing_to_nrs(
    *,
    session: Session,
    filing: Filing,
    language: str = "en",
    client: NRSClient | None = None,
) -> SubmissionOutcome:
    """End-to-end: build pack → sign + POST → parse → persist."""
    if filing.audit_status == "red":
        raise SubmissionConfigError(
            "Audit Shield status is red. Resolve findings before submitting."
        )
    if filing.audit_status == "pending":
        raise SubmissionConfigError(
            "Run Audit Shield on this filing before submitting to NRS."
        )

    # Rebuild the canonical pack from the stored return JSON. This keeps
    # the NRS submission byte-equal to the pack the Audit Shield approved.
    return_ = PITReturn.model_validate(filing.return_json)
    pack = build_canonical_pack(return_)

    use_simulation = False
    nrs_client = client
    if nrs_client is None:
        try:
            nrs_client = build_default_nrs_client()
        except Exception as exc:  # extreme safety — shouldn't raise at construct
            log.warning("failed to build NRS client: %s", exc)
            nrs_client = None

    if nrs_client is None:
        use_simulation = True
    else:
        # If creds are missing, NRSClient.submit_filing raises NRSAuthError.
        # We catch that and drop into simulation.
        try:
            nrs_client._credentials.assert_present()  # noqa: SLF001
        except NRSAuthError:
            use_simulation = True

    if use_simulation:
        return _persist_simulated(session=session, filing=filing, pack=pack)

    try:
        result = nrs_client.submit_filing(pack)
    except NRSTransportError as exc:
        return _persist_error(
            session=session,
            filing=filing,
            code="NRS-UPSTREAM-DOWN",
            message=str(exc),
            language=language,
        )

    if isinstance(result, NRSResponse):
        return _persist_accepted(session=session, filing=filing, response=result)
    # NRSRejection
    return _persist_rejected(
        session=session, filing=filing, rejection=result, language=language
    )


def _persist_accepted(
    *, session: Session, filing: Filing, response: NRSResponse
) -> SubmissionOutcome:
    filing.submission_status = "accepted"
    filing.nrs_irn = response.irn or None
    filing.nrs_csid = response.csid or None
    filing.nrs_qr_payload = response.qr_payload or None
    filing.nrs_submission_error = None
    filing.nrs_submitted_at = datetime.now(timezone.utc)
    session.commit()
    return SubmissionOutcome(
        filing_id=filing.id,
        status="accepted",
        irn=response.irn,
        csid=response.csid,
        qr_payload=response.qr_payload,
        raw=response.raw,
    )


def _persist_rejected(
    *,
    session: Session,
    filing: Filing,
    rejection: NRSRejection,
    language: str,
) -> SubmissionOutcome:
    translated = translate_error(code=rejection.code, language=language)
    filing.submission_status = "rejected"
    filing.nrs_submission_error = json.dumps(
        {**translated, "vendor_message": rejection.message}
    )
    filing.nrs_submitted_at = datetime.now(timezone.utc)
    session.commit()
    return SubmissionOutcome(
        filing_id=filing.id,
        status="rejected",
        error={**translated, "vendor_message": rejection.message},
        raw=rejection.raw,
    )


def _persist_error(
    *,
    session: Session,
    filing: Filing,
    code: str,
    message: str,
    language: str,
) -> SubmissionOutcome:
    translated = translate_error(code=code, language=language)
    filing.submission_status = "error"
    filing.nrs_submission_error = json.dumps({**translated, "detail": message})
    filing.nrs_submitted_at = datetime.now(timezone.utc)
    session.commit()
    return SubmissionOutcome(
        filing_id=filing.id,
        status="error",
        error={**translated, "detail": message},
    )


def _persist_simulated(
    *, session: Session, filing: Filing, pack: dict[str, Any]
) -> SubmissionOutcome:
    """Generate deterministic IRN / CSID / QR values when NRS creds are missing.

    Values are clearly labelled `SIM-...` so downstream UI can render a
    'simulated' badge and the Audit Shield / operator trail sees the
    submission was not a real NRS transaction.
    """
    digest = hashlib.sha256(
        json.dumps(pack, sort_keys=True).encode("utf-8")
    ).hexdigest()
    irn = f"SIM-IRN-{digest[:16].upper()}"
    csid = f"SIM-CSID-{digest[16:48].upper()}"
    qr_payload = (
        f"mai-filer://sim/irn/{irn}?csid={csid}&filing={filing.id}"
    )

    filing.submission_status = "simulated"
    filing.nrs_irn = irn
    filing.nrs_csid = csid
    filing.nrs_qr_payload = qr_payload
    filing.nrs_submission_error = None
    filing.nrs_submitted_at = datetime.now(timezone.utc)
    session.commit()
    return SubmissionOutcome(
        filing_id=filing.id,
        status="simulated",
        irn=irn,
        csid=csid,
        qr_payload=qr_payload,
        simulated=True,
    )


def generate_sim_receipt_id() -> str:
    """Helper for tests that need a simulation IRN without a full run."""
    return f"SIM-IRN-{uuid.uuid4().hex[:16].upper()}"
