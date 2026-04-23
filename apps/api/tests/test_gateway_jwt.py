"""NRS JWT signer tests (P7.4)."""

from __future__ import annotations

import hashlib
import time

import jwt as pyjwt
import pytest

from app.gateway.jwt_signing import (
    DEFAULT_TTL_SECONDS,
    JWTSigningError,
    sign_jwt,
    verify_jwt,
)


BASE = {
    "payload": '{"tax_year":2026,"net_payable":"40000.00"}',
    "business_id": "biz-42",
    "issuer": "mai-filer",
    "audience": "https://api.nrs.gov.ng/v1",
    "secret_or_private_key": "a-long-shared-secret-for-hs256",
}


def test_sign_and_verify_roundtrip() -> None:
    token = sign_jwt(**BASE)
    claims = verify_jwt(
        token=token,
        payload=BASE["payload"],
        issuer=BASE["issuer"],
        audience=BASE["audience"],
        secret_or_public_key=BASE["secret_or_private_key"],
    )
    assert claims["sub"] == "biz-42"
    assert claims["iss"] == "mai-filer"
    assert claims["aud"] == BASE["audience"]
    assert claims["sha256"] == hashlib.sha256(
        BASE["payload"].encode("utf-8")
    ).hexdigest()
    assert "jti" in claims


def test_ttl_default_is_five_minutes() -> None:
    assert DEFAULT_TTL_SECONDS == 300


def test_signed_payload_binding_rejects_tampered_body() -> None:
    token = sign_jwt(**BASE)
    with pytest.raises(JWTSigningError) as exc:
        verify_jwt(
            token=token,
            payload=BASE["payload"] + "TAMPER",
            issuer=BASE["issuer"],
            audience=BASE["audience"],
            secret_or_public_key=BASE["secret_or_private_key"],
        )
    assert "sha256" in str(exc.value)


def test_verify_rejects_wrong_audience() -> None:
    token = sign_jwt(**BASE)
    with pytest.raises(JWTSigningError):
        verify_jwt(
            token=token,
            payload=BASE["payload"],
            issuer=BASE["issuer"],
            audience="https://other.nrs",
            secret_or_public_key=BASE["secret_or_private_key"],
        )


def test_verify_rejects_wrong_issuer() -> None:
    token = sign_jwt(**BASE)
    with pytest.raises(JWTSigningError):
        verify_jwt(
            token=token,
            payload=BASE["payload"],
            issuer="other-issuer",
            audience=BASE["audience"],
            secret_or_public_key=BASE["secret_or_private_key"],
        )


def test_verify_rejects_expired_token() -> None:
    past = time.time() - 2 * DEFAULT_TTL_SECONDS
    token = sign_jwt(**BASE, now=past)
    with pytest.raises(JWTSigningError) as exc:
        verify_jwt(
            token=token,
            payload=BASE["payload"],
            issuer=BASE["issuer"],
            audience=BASE["audience"],
            secret_or_public_key=BASE["secret_or_private_key"],
        )
    assert "expired" in str(exc.value).lower()


def test_sign_refuses_empty_key() -> None:
    args = {**BASE, "secret_or_private_key": ""}
    with pytest.raises(JWTSigningError):
        sign_jwt(**args)


def test_sign_refuses_empty_business_id() -> None:
    args = {**BASE, "business_id": ""}
    with pytest.raises(JWTSigningError):
        sign_jwt(**args)


def test_sign_emits_pyjwt_compatible_token() -> None:
    """Sanity — our token decodes with vanilla PyJWT."""
    token = sign_jwt(**BASE)
    decoded = pyjwt.decode(
        token,
        BASE["secret_or_private_key"],
        algorithms=["HS256"],
        audience=BASE["audience"],
    )
    assert decoded["sub"] == "biz-42"
