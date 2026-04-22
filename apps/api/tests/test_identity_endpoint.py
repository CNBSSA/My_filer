"""Identity endpoint tests — overrides the service via build_identity_service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.identity import get_service
from app.identity.base import NINVerification
from app.identity.service import IdentityService
from app.main import app
from tests.test_identity_service import ScriptedAggregator, _happy_verification

pytestmark = pytest.mark.usefixtures("override_db")


def _install_service(db_session, aggregator) -> None:
    svc = IdentityService(
        aggregator=aggregator,
        session=db_session,
        hash_salt="endpoint-salt",
        vault_key="endpoint-key-long-enough",
        sleep=lambda _s: None,
    )
    app.dependency_overrides[get_service] = lambda: svc


def test_verify_endpoint_happy_path(db_session) -> None:
    _install_service(db_session, ScriptedAggregator([_happy_verification()]))
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/identity/verify",
            json={
                "nin": "12345678901",
                "consent": True,
                "declared_name": "Chidi Okafor",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["verified"] is True
        assert body["full_name"] == "Chidi Emeka Okafor"
        assert body["name_match_status"] == "fuzzy"
        assert body["consent_log_id"] is not None
    finally:
        app.dependency_overrides.clear()


def test_verify_endpoint_refuses_without_consent() -> None:
    # No service override needed — handler rejects before dispatch.
    client = TestClient(app)
    response = client.post(
        "/v1/identity/verify",
        json={"nin": "12345678901", "consent": False},
    )
    assert response.status_code == 400


def test_verify_endpoint_rejects_invalid_nin_format() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/identity/verify",
        json={"nin": "abc", "consent": True},
    )
    assert response.status_code == 422


def test_verify_endpoint_bubbles_rejection_as_200_with_verified_false(db_session) -> None:
    rejected = NINVerification(
        valid=False,
        aggregator="scripted",
        nin="12345678901",
        error="NIN not found",
    )
    _install_service(db_session, ScriptedAggregator([rejected]))
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/identity/verify",
            json={"nin": "12345678901", "consent": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["verified"] is False
        assert body["error"] == "NIN not found"
    finally:
        app.dependency_overrides.clear()
