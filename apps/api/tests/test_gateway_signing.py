"""NRS signing tests (P6.1)."""

from __future__ import annotations

import pytest

from app.gateway.signing import SigningError, sign_request, verify_signature


def test_sign_is_deterministic() -> None:
    a = sign_request(payload='{"a":1}', timestamp="2026-04-22T10:00:00.000Z", secret="k")
    b = sign_request(payload='{"a":1}', timestamp="2026-04-22T10:00:00.000Z", secret="k")
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_sign_is_secret_sensitive() -> None:
    a = sign_request(payload="p", timestamp="t", secret="k1")
    b = sign_request(payload="p", timestamp="t", secret="k2")
    assert a != b


def test_sign_is_timestamp_sensitive() -> None:
    a = sign_request(payload="p", timestamp="t1", secret="k")
    b = sign_request(payload="p", timestamp="t2", secret="k")
    assert a != b


def test_sign_is_payload_sensitive() -> None:
    a = sign_request(payload="p1", timestamp="t", secret="k")
    b = sign_request(payload="p2", timestamp="t", secret="k")
    assert a != b


def test_sign_refuses_empty_secret() -> None:
    with pytest.raises(SigningError):
        sign_request(payload="p", timestamp="t", secret="")


def test_verify_signature_roundtrip() -> None:
    sig = sign_request(payload="p", timestamp="t", secret="k")
    assert verify_signature(payload="p", timestamp="t", secret="k", signature=sig) is True


def test_verify_signature_rejects_mismatch() -> None:
    sig = sign_request(payload="p", timestamp="t", secret="k")
    assert verify_signature(
        payload="p", timestamp="t", secret="k", signature=sig[:-1] + "0"
    ) is False
    assert verify_signature(
        payload="p!", timestamp="t", secret="k", signature=sig
    ) is False
