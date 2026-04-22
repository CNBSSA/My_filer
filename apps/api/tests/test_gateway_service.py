"""Gateway service tests — orchestration, simulation, persistence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.db.models import Filing
from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity
from app.gateway.client import (
    NRSClient,
    NRSCredentials,
    NRSRejection,
    NRSResponse,
    NRSTransportError,
)
from app.gateway.service import (
    SubmissionConfigError,
    submit_filing_to_nrs,
)

pytestmark = pytest.mark.usefixtures("override_db")


def _filing_payload() -> dict:
    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
        ),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
        ],
        declaration=True,
    ).model_dump(mode="json")


def _green_filing(db_session) -> Filing:
    f = Filing(
        tax_year=2026,
        return_json=_filing_payload(),
        audit_status="green",
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


class StubClient:
    """Bypasses HTTP; returns a preset outcome from submit_filing."""

    def __init__(self, outcome) -> None:
        self._outcome = outcome
        self._credentials = NRSCredentials(
            client_id="x", client_secret="y", business_id="z"
        )
        self.calls: list[dict] = []

    def submit_filing(self, pack, *, path="/efiling/pit/submit"):
        self.calls.append({"pack": pack, "path": path})
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_submit_refuses_red_audit(db_session) -> None:
    f = Filing(tax_year=2026, return_json=_filing_payload(), audit_status="red")
    db_session.add(f)
    db_session.commit()
    with pytest.raises(SubmissionConfigError):
        submit_filing_to_nrs(session=db_session, filing=f, client=StubClient(None))


def test_submit_refuses_pending_audit(db_session) -> None:
    f = Filing(tax_year=2026, return_json=_filing_payload(), audit_status="pending")
    db_session.add(f)
    db_session.commit()
    with pytest.raises(SubmissionConfigError):
        submit_filing_to_nrs(session=db_session, filing=f, client=StubClient(None))


def test_submit_happy_path_persists_receipt(db_session) -> None:
    f = _green_filing(db_session)
    outcome = submit_filing_to_nrs(
        session=db_session,
        filing=f,
        client=StubClient(
            NRSResponse(
                irn="NRS-IRN-001",
                csid="CSID-001",
                qr_payload="nrs://verify/NRS-IRN-001",
                raw={},
            )
        ),
    )
    assert outcome.status == "accepted"
    assert outcome.irn == "NRS-IRN-001"

    db_session.refresh(f)
    assert f.submission_status == "accepted"
    assert f.nrs_irn == "NRS-IRN-001"
    assert f.nrs_csid == "CSID-001"
    assert f.nrs_qr_payload == "nrs://verify/NRS-IRN-001"
    assert f.nrs_submission_error is None
    assert f.nrs_submitted_at is not None


def test_submit_rejection_persists_translated_error(db_session) -> None:
    f = _green_filing(db_session)
    outcome = submit_filing_to_nrs(
        session=db_session,
        filing=f,
        client=StubClient(
            NRSRejection(code="NRS-NIN-NOT-FOUND", message="NIN sync pending")
        ),
    )
    assert outcome.status == "rejected"
    assert outcome.error is not None
    assert outcome.error["code"] == "NRS-NIN-NOT-FOUND"
    assert outcome.error["severity"] == "user_fix"
    assert "NIN sync pending" == outcome.error["vendor_message"]

    db_session.refresh(f)
    assert f.submission_status == "rejected"
    assert f.nrs_submission_error is not None
    assert "NRS-NIN-NOT-FOUND" in f.nrs_submission_error


def test_submit_transport_error_persists_error_entry(db_session) -> None:
    f = _green_filing(db_session)
    outcome = submit_filing_to_nrs(
        session=db_session,
        filing=f,
        client=StubClient(NRSTransportError("upstream exhausted")),
    )
    assert outcome.status == "error"
    assert outcome.error is not None
    assert outcome.error["code"] == "NRS-UPSTREAM-DOWN"
    db_session.refresh(f)
    assert f.submission_status == "error"


def test_submit_falls_back_to_simulation_without_creds(db_session) -> None:
    """When no client is injected and factory-built creds are empty, the
    service runs a deterministic simulation so local dev still works."""
    f = _green_filing(db_session)
    # Factory builds the default client, which will raise NRSAuthError at
    # submit-time because env vars are empty in tests.
    outcome = submit_filing_to_nrs(session=db_session, filing=f)
    assert outcome.status == "simulated"
    assert outcome.simulated is True
    assert outcome.irn is not None and outcome.irn.startswith("SIM-IRN-")
    assert outcome.csid is not None and outcome.csid.startswith("SIM-CSID-")
    assert outcome.qr_payload is not None
    assert outcome.qr_payload.startswith("mai-filer://sim/irn/")

    db_session.refresh(f)
    assert f.submission_status == "simulated"
    assert f.nrs_irn and f.nrs_csid and f.nrs_qr_payload


def test_simulation_receipts_have_stable_shape(db_session) -> None:
    """SIM IRN / CSID have predictable prefixes + lengths; QR encodes the filing."""
    f1 = _green_filing(db_session)
    f2 = _green_filing(db_session)
    o1 = submit_filing_to_nrs(session=db_session, filing=f1)
    o2 = submit_filing_to_nrs(session=db_session, filing=f2)
    assert o1.irn and o1.irn.startswith("SIM-IRN-") and len(o1.irn) == len("SIM-IRN-") + 16
    assert o1.csid and o1.csid.startswith("SIM-CSID-")
    assert o2.irn and o2.irn.startswith("SIM-IRN-")
    # Each filing gets its own QR (keyed by filing id).
    assert f1.id in (o1.qr_payload or "")
    assert f2.id in (o2.qr_payload or "")
    assert o1.qr_payload != o2.qr_payload
