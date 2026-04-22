"""Identity service tests (P5.5)."""

from __future__ import annotations

from datetime import date

import pytest

from app.db.models import ConsentLog, IdentityRecord
from app.identity.base import AggregatorError, NINVerification
from app.identity.service import (
    ConsentRequiredError,
    IdentityService,
)

pytestmark = pytest.mark.usefixtures("override_db")


NIN = "12345678901"
SALT = "test-salt"
KEY = "test-vault-key-long-enough-to-be-random"


class ScriptedAggregator:
    """Plays a fixed script of (verification | exception)."""

    name = "scripted"

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def verify_nin(self, nin: str, *, consent: bool) -> NINVerification:
        self.calls.append({"nin": nin, "consent": consent})
        if not self._script:
            raise AssertionError("script exhausted")
        head = self._script.pop(0)
        if isinstance(head, Exception):
            raise head
        return head


def _happy_verification() -> NINVerification:
    return NINVerification(
        valid=True,
        aggregator="scripted",
        nin=NIN,
        first_name="Chidi",
        middle_name="Emeka",
        last_name="Okafor",
        full_name="Chidi Emeka Okafor",
        date_of_birth=date(1990, 4, 12),
        gender="M",
        state_of_origin="Anambra",
    )


def _service(db_session, aggregator) -> IdentityService:
    return IdentityService(
        aggregator=aggregator,
        session=db_session,
        hash_salt=SALT,
        vault_key=KEY,
        sleep=lambda _s: None,  # don't actually sleep in tests
    )


def test_verify_refuses_when_consent_false(db_session) -> None:
    svc = _service(db_session, ScriptedAggregator([_happy_verification()]))
    with pytest.raises(ConsentRequiredError):
        svc.verify_taxpayer(nin=NIN, consent=False)


def test_verify_rejects_invalid_nin(db_session) -> None:
    svc = _service(db_session, ScriptedAggregator([_happy_verification()]))
    with pytest.raises(ValueError):
        svc.verify_taxpayer(nin="abc", consent=True)


def test_verify_happy_path_upserts_identity_and_logs_consent(db_session) -> None:
    svc = _service(db_session, ScriptedAggregator([_happy_verification()]))
    result = svc.verify_taxpayer(
        nin=NIN, consent=True, declared_name="Chidi Okafor"
    )
    assert result.verified is True
    assert result.full_name == "Chidi Emeka Okafor"
    assert result.name_match_status == "fuzzy"
    assert result.attempts == 1

    record = db_session.get(IdentityRecord, result.nin_hash)
    assert record is not None
    assert record.full_name == "Chidi Emeka Okafor"
    # Raw NIN is never persisted — only the ciphertext.
    assert record.nin_ciphertext != NIN
    assert NIN not in record.nin_ciphertext

    logs = db_session.query(ConsentLog).all()
    assert len(logs) == 1
    assert logs[0].outcome == "verified"
    assert logs[0].consent_granted is True
    assert logs[0].name_match_status == "fuzzy"


def test_verify_retries_transport_errors_then_succeeds(db_session) -> None:
    aggregator = ScriptedAggregator(
        [
            AggregatorError("transient"),
            AggregatorError("still transient"),
            _happy_verification(),
        ]
    )
    svc = _service(db_session, aggregator)
    result = svc.verify_taxpayer(nin=NIN, consent=True)
    assert result.verified is True
    assert result.attempts == 3


def test_verify_retries_exhausted_logs_error(db_session) -> None:
    aggregator = ScriptedAggregator(
        [AggregatorError("upstream 503")] * 10  # more than retries
    )
    svc = _service(db_session, aggregator)
    result = svc.verify_taxpayer(nin=NIN, consent=True)
    assert result.verified is False
    assert result.attempts == 5  # 1 initial + 4 retries
    assert result.error is not None
    logs = db_session.query(ConsentLog).all()
    assert len(logs) == 1
    assert logs[0].outcome == "error"


def test_verify_clean_rejection_does_not_retry(db_session) -> None:
    """Vendor saying 'not found' should NOT burn retries."""
    rejected = NINVerification(
        valid=False,
        aggregator="scripted",
        nin=NIN,
        error="NIN not found",
    )
    aggregator = ScriptedAggregator([rejected])
    svc = _service(db_session, aggregator)
    result = svc.verify_taxpayer(nin=NIN, consent=True)
    assert result.verified is False
    assert result.attempts == 1
    logs = db_session.query(ConsentLog).all()
    assert logs[0].outcome == "rejected"


def test_verify_name_mismatch_marks_status(db_session) -> None:
    svc = _service(db_session, ScriptedAggregator([_happy_verification()]))
    result = svc.verify_taxpayer(
        nin=NIN, consent=True, declared_name="Grace Ibrahim"
    )
    assert result.verified is True  # NIN is real
    assert result.name_match_status == "mismatch"
    logs = db_session.query(ConsentLog).all()
    assert logs[0].name_match_status == "mismatch"
