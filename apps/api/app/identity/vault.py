"""NIN hashing + encrypted vault (P5.6).

Per `docs/COMPLIANCE.md §1`, the raw NIN is NEVER persisted in the primary
database. We keep:

1. A **salted SHA-256 hash** for lookup (e.g., "has this NIN already been
   verified?"). The salt is stable per environment (`NIN_HASH_SALT`) so
   the same NIN hashes to the same value across calls.
2. A **Fernet ciphertext** of the raw NIN, keyed with `NIN_VAULT_KEY`.
   The ciphertext is the only persisted form of the raw value. Rotating
   `NIN_VAULT_KEY` invalidates all previously-stored ciphertexts.

The vault writer is separated from the hash so the service layer can:
- hash every NIN for consent-log keying (cheap, deterministic),
- only vault when the aggregator returned a *valid* record.

All operations are pure — no DB / no I/O — which keeps the test surface
small and makes rotation scripts trivial.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class VaultKeyError(ValueError):
    """Raised when NIN_VAULT_KEY is missing or mis-shaped."""


class VaultDecryptError(ValueError):
    """Raised when ciphertext cannot be decrypted with the current key."""


def hash_nin(nin: str, *, salt: str) -> str:
    """Return the hex digest of `HMAC_SHA256(salt, nin)`.

    HMAC is preferred over plain SHA-256(salt || nin) because it resists
    length-extension attacks and has a clean keyed-hash semantics.
    """
    _require_nin(nin)
    if not salt:
        raise ValueError("hash_nin salt must be non-empty")
    return hmac.new(salt.encode("utf-8"), nin.encode("utf-8"), hashlib.sha256).hexdigest()


def _coerce_fernet_key(key: str) -> bytes:
    """Accept either a raw 32-byte base64 Fernet key or a raw 32-byte
    secret we'll base64 ourselves."""
    raw = key.encode("utf-8")
    # If already a valid Fernet token key (urlsafe-base64 of 32 bytes), use as is.
    try:
        if len(base64.urlsafe_b64decode(raw)) == 32:
            return raw
    except Exception:
        pass
    # Otherwise hash the input to 32 bytes and base64 it.
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet(key: str) -> Fernet:
    if not key:
        raise VaultKeyError(
            "NIN_VAULT_KEY is missing. Set a 32-byte base64 Fernet key in the environment."
        )
    try:
        return Fernet(_coerce_fernet_key(key))
    except Exception as exc:
        raise VaultKeyError(f"NIN_VAULT_KEY is invalid: {exc}") from exc


def encrypt_nin(nin: str, *, key: str) -> str:
    """Return a Fernet token (str) that encrypts `nin`."""
    _require_nin(nin)
    token = _fernet(key).encrypt(nin.encode("utf-8"))
    return token.decode("ascii")


def decrypt_nin(token: str, *, key: str) -> str:
    """Decrypt a Fernet token back to the raw NIN. Raises on mismatch."""
    try:
        raw = _fernet(key).decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise VaultDecryptError("ciphertext does not match the current key") from exc
    return raw.decode("utf-8")


def _require_nin(nin: str) -> None:
    if not isinstance(nin, str) or not nin.isdigit() or len(nin) != 11:
        raise ValueError("NIN must be exactly 11 digits")


__all__ = [
    "VaultDecryptError",
    "VaultKeyError",
    "decrypt_nin",
    "encrypt_nin",
    "hash_nin",
]
