"""NIN vault tests (P5.6)."""

from __future__ import annotations

import pytest

from app.identity.vault import (
    VaultDecryptError,
    VaultKeyError,
    decrypt_nin,
    encrypt_nin,
    hash_nin,
)

SALT = "mai-filer-test-salt-v1"
KEY = "a-pretty-long-dev-only-secret-value-please-rotate"
OTHER_KEY = "a-completely-different-dev-only-secret-value"


def test_hash_nin_is_deterministic() -> None:
    a = hash_nin("12345678901", salt=SALT)
    b = hash_nin("12345678901", salt=SALT)
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_hash_nin_is_salt_sensitive() -> None:
    a = hash_nin("12345678901", salt=SALT)
    b = hash_nin("12345678901", salt="other-salt")
    assert a != b


def test_hash_nin_rejects_non_11_digits() -> None:
    with pytest.raises(ValueError):
        hash_nin("123", salt=SALT)
    with pytest.raises(ValueError):
        hash_nin("abcdefghijk", salt=SALT)


def test_encrypt_then_decrypt_roundtrip() -> None:
    token = encrypt_nin("12345678901", key=KEY)
    assert token  # non-empty
    assert decrypt_nin(token, key=KEY) == "12345678901"


def test_decrypt_with_wrong_key_fails() -> None:
    token = encrypt_nin("12345678901", key=KEY)
    with pytest.raises(VaultDecryptError):
        decrypt_nin(token, key=OTHER_KEY)


def test_missing_key_raises() -> None:
    with pytest.raises(VaultKeyError):
        encrypt_nin("12345678901", key="")


def test_hash_and_encrypt_are_independent() -> None:
    """Same NIN, different envs: hash differs (salt) and ciphertext differs (key)."""
    h1 = hash_nin("12345678901", salt="salt1")
    h2 = hash_nin("12345678901", salt="salt2")
    c1 = encrypt_nin("12345678901", key="key1")
    c2 = encrypt_nin("12345678901", key="key2")
    assert h1 != h2
    assert c1 != c2
