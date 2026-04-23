"""CAC Part-A verification tests (P9).

Covers the three layers:
  1. `DojahAdapter.verify_cac` — HTTP response → CACVerification mapping
  2. `IdentityService.verify_organization` — retry loop + consent log +
     `cac_records` upsert + name-match
  3. `POST /v1/identity/verify-cac` endpoint + `verify_cac` Mai tool
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db.models import CACRecord, ConsentLog
from app.identity.base import (
    AggregatorError,
    CACDirector,
    CACVerification,
    NINVerification,
)
from app.identity.dojah import DojahAdapter
from app.identity.service import ConsentRequiredError, IdentityService
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


RC = "RC-987654"
SALT = "test-salt"
KEY = "test-vault-key-long-enough-to-be-random"


# ---------------------------------------------------------------------------
# Layer 1 — Dojah adapter
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, *, status_code: int, body=None) -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = body if isinstance(body, str) else ""

    def json(self):
        return self._body if isinstance(self._body, dict) else {}


class FakeHttp:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def get(self, url, *, headers, params, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _adapter(response):
    http = FakeHttp(response)
    return (
        DojahAdapter(api_key="test-key", app_id="test-app", http=http),
        http,
    )


def test_dojah_cac_happy_path_maps_entity() -> None:
    adapter, http = _adapter(
        FakeResponse(
            status_code=200,
            body={
                "entity": {
                    "rc_number": RC,
                    "company_name": "Globacom Limited",
                    "company_type": "LTD",
                    "registration_date": "2008-09-15",
                    "status": "ACTIVE",
                    "address": "1 Mike Adenuga Way, Lagos",
                    "email": "info@globacom.ng",
                    "directors": [
                        {"name": "John Doe", "role": "Director", "nationality": "NG"},
                        {"name": "Jane Roe", "role": "Secretary"},
                    ],
                }
            },
        )
    )
    result = adapter.verify_cac(RC, consent=True)
    assert result.valid is True
    assert result.aggregator == "dojah"
    assert result.company_name == "Globacom Limited"
    assert result.company_type == "LTD"
    assert result.status == "ACTIVE"
    assert result.registration_date == date(2008, 9, 15)
    assert len(result.directors) == 2
    assert result.directors[0].name == "John Doe"
    call = http.calls[0]
    assert call["url"].endswith("/kyc/cac/advance")
    assert call["params"] == {"rc_number": RC}


def test_dojah_cac_requires_consent() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=200, body={"entity": {}}))
    with pytest.raises(PermissionError):
        adapter.verify_cac(RC, consent=False)


def test_dojah_cac_validates_rc() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=200, body={}))
    with pytest.raises(ValueError):
        adapter.verify_cac("", consent=True)
    with pytest.raises(ValueError):
        adapter.verify_cac("bad rc!", consent=True)


def test_dojah_cac_4xx_returns_invalid() -> None:
    adapter, _ = _adapter(
        FakeResponse(status_code=404, body={"error": "RC not found"})
    )
    result = adapter.verify_cac(RC, consent=True)
    assert result.valid is False
    assert "RC not found" in (result.error or "")


def test_dojah_cac_5xx_escalates() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=503, body="upstream down"))
    with pytest.raises(AggregatorError):
        adapter.verify_cac(RC, consent=True)


def test_dojah_cac_dissolved_status_marks_invalid() -> None:
    adapter, _ = _adapter(
        FakeResponse(
            status_code=200,
            body={
                "entity": {
                    "rc_number": RC,
                    "company_name": "Ghost Co",
                    "status": "DISSOLVED",
                }
            },
        )
    )
    result = adapter.verify_cac(RC, consent=True)
    assert result.valid is False
    assert result.status == "DISSOLVED"


# ---------------------------------------------------------------------------
# Layer 2 — IdentityService.verify_organization
# ---------------------------------------------------------------------------


class ScriptedCACAggregator:
    name = "scripted"

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def verify_nin(self, nin: str, *, consent: bool) -> NINVerification:
        raise AssertionError("verify_nin not exercised in this test file")

    def verify_cac(self, rc_number: str, *, consent: bool) -> CACVerification:
        self.calls.append({"rc_number": rc_number, "consent": consent})
        if not self._script:
            raise AssertionError("script exhausted")
        head = self._script.pop(0)
        if isinstance(head, Exception):
            raise head
        return head


def _happy_cac(rc: str = RC) -> CACVerification:
    return CACVerification(
        valid=True,
        aggregator="scripted",
        rc_number=rc,
        company_name="Globacom Limited",
        company_type="LTD",
        status="ACTIVE",
        registration_date=date(2008, 9, 15),
        address="1 Mike Adenuga Way, Lagos",
        email="info@globacom.ng",
        directors=[CACDirector(name="John Doe", role="Director")],
    )


def _service(db_session, aggregator) -> IdentityService:
    return IdentityService(
        aggregator=aggregator,
        session=db_session,
        hash_salt=SALT,
        vault_key=KEY,
        sleep=lambda _s: None,
    )


def test_service_cac_refuses_without_consent(db_session) -> None:
    svc = _service(db_session, ScriptedCACAggregator([_happy_cac()]))
    with pytest.raises(ConsentRequiredError):
        svc.verify_organization(rc_number=RC, consent=False)


def test_service_cac_rejects_invalid_rc(db_session) -> None:
    svc = _service(db_session, ScriptedCACAggregator([]))
    with pytest.raises(ValueError):
        svc.verify_organization(rc_number=" ", consent=True)


def test_service_cac_happy_path_upserts_and_logs(db_session) -> None:
    svc = _service(db_session, ScriptedCACAggregator([_happy_cac()]))
    result = svc.verify_organization(
        rc_number=RC, consent=True, declared_name="Globacom Limited"
    )
    assert result.verified is True
    assert result.company_name == "Globacom Limited"
    assert result.name_match_status == "strict"
    assert result.attempts == 1
    assert result.directors[0]["name"] == "John Doe"

    record = db_session.get(CACRecord, RC)
    assert record is not None
    assert record.company_name == "Globacom Limited"
    assert record.directors_json[0]["name"] == "John Doe"

    logs = db_session.query(ConsentLog).all()
    assert len(logs) == 1
    assert logs[0].outcome == "verified"
    assert logs[0].nin_hash == RC  # CAC reuses the column
    assert logs[0].purpose == "corporate_filing"


def test_service_cac_retries_transport_errors(db_session) -> None:
    aggregator = ScriptedCACAggregator(
        [AggregatorError("transient"), AggregatorError("still"), _happy_cac()]
    )
    svc = _service(db_session, aggregator)
    result = svc.verify_organization(rc_number=RC, consent=True)
    assert result.verified is True
    assert result.attempts == 3


def test_service_cac_clean_rejection_does_not_retry(db_session) -> None:
    rejected = CACVerification(
        valid=False,
        aggregator="scripted",
        rc_number=RC,
        error="RC not found",
    )
    svc = _service(db_session, ScriptedCACAggregator([rejected]))
    result = svc.verify_organization(rc_number=RC, consent=True)
    assert result.verified is False
    assert result.attempts == 1
    logs = db_session.query(ConsentLog).all()
    assert logs[0].outcome == "rejected"
    assert "RC not found" in (result.error or "")


def test_service_cac_name_mismatch_marks_status(db_session) -> None:
    svc = _service(db_session, ScriptedCACAggregator([_happy_cac()]))
    result = svc.verify_organization(
        rc_number=RC, consent=True, declared_name="Totally Different Co Ltd"
    )
    assert result.verified is True
    assert result.name_match_status == "mismatch"


def test_service_cac_normalizes_rc_number(db_session) -> None:
    """Mixed-case + whitespace should collapse to a stable upper-case key."""
    svc = _service(
        db_session,
        ScriptedCACAggregator([_happy_cac(rc="RC-987654")]),
    )
    result = svc.verify_organization(rc_number="  rc-987654  ", consent=True)
    assert result.rc_number == "RC-987654"
    assert db_session.get(CACRecord, "RC-987654") is not None


# ---------------------------------------------------------------------------
# Layer 3 — HTTP endpoint + Mai tool
# ---------------------------------------------------------------------------


def test_verify_cac_endpoint_requires_consent_flag() -> None:
    client = TestClient(app)
    resp = client.post("/v1/identity/verify-cac", json={"rc_number": RC, "consent": False})
    assert resp.status_code == 400


def test_verify_cac_endpoint_maps_aggregator_error_to_502(monkeypatch) -> None:
    """The default Dojah adapter talks to dev-missing creds which will raise
    AggregatorError — the endpoint should translate that to a 502, not 500."""
    from app.api import identity as identity_api

    class BustedSvc:
        def verify_organization(self, **kwargs):
            raise AggregatorError("no sandbox creds")

    app.dependency_overrides[identity_api.get_service] = lambda: BustedSvc()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/identity/verify-cac",
            json={"rc_number": RC, "consent": True},
        )
        assert resp.status_code == 502
        assert "no sandbox creds" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(identity_api.get_service, None)


def test_verify_cac_endpoint_happy_path(monkeypatch) -> None:
    from app.api import identity as identity_api
    from app.identity.service import CACVerificationResult

    class StubSvc:
        def verify_organization(self, **kwargs):
            return CACVerificationResult(
                verified=True,
                aggregator="stub",
                rc_number=RC,
                company_name="Globacom Limited",
                status="ACTIVE",
                directors=[{"name": "John Doe", "role": "Director"}],
                name_match_status="strict",
                attempts=1,
                consent_log_id="log-1",
            )

    app.dependency_overrides[identity_api.get_service] = lambda: StubSvc()
    try:
        client = TestClient(app)
        resp = client.post(
            "/v1/identity/verify-cac",
            json={"rc_number": RC, "consent": True, "declared_name": "Globacom Limited"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verified"] is True
        assert body["company_name"] == "Globacom Limited"
        assert body["name_match_status"] == "strict"
    finally:
        app.dependency_overrides.pop(identity_api.get_service, None)


def test_mai_tool_verify_cac_dispatches(monkeypatch) -> None:
    """The `verify_cac` Mai tool routes through the service and returns JSON."""
    from app.agents.mai_filer import tools as tool_mod
    from app.identity.service import CACVerificationResult

    captured: dict = {}

    class StubSvc:
        def verify_organization(self, **kwargs):
            captured.update(kwargs)
            return CACVerificationResult(
                verified=True,
                aggregator="stub",
                rc_number=RC,
                company_name="Globacom Limited",
                attempts=1,
            )

    monkeypatch.setattr(tool_mod, "build_identity_service", lambda _s: StubSvc())

    raw = tool_mod.run_tool(
        "verify_cac",
        {"rc_number": RC, "consent": True, "declared_name": "Globacom Limited"},
    )
    payload = json.loads(raw)
    assert payload["verified"] is True
    assert payload["company_name"] == "Globacom Limited"
    assert captured["rc_number"] == RC
    assert captured["consent"] is True
