"""NRS request signing (P6.1).

Per `docs/KNOWLEDGE_BASE.md §9`:

    Signature = HMAC_SHA256(payload + timestamp, secret).hex()

and the NRS expects three headers on every call:

    X-API-Key        <client_id>
    X-API-Timestamp  <ISO-20022 timestamp>
    X-API-Signature  <hex-digest>

The signer is pure — it never touches the network, never logs the secret,
and uses `hmac.compare_digest` for verification to avoid timing leaks.

The NRS may swap to JWT after the Rev360 cutover. When that lands, add a
`sign_jwt()` sibling here and let the client select per env flag; the
rest of the gateway stays unchanged.
"""

from __future__ import annotations

import hashlib
import hmac


class SigningError(ValueError):
    """Raised when the signer cannot produce or verify a signature."""


def sign_request(*, payload: str, timestamp: str, secret: str) -> str:
    """Return the hex HMAC-SHA256 over `payload + timestamp`.

    `payload` should be the canonical JSON body (no trailing whitespace).
    `timestamp` must be the same string you put in `X-API-Timestamp`.
    """
    if not secret:
        raise SigningError("secret is empty — refusing to sign")
    if not isinstance(payload, str) or not isinstance(timestamp, str):
        raise SigningError("payload and timestamp must be strings")

    message = (payload + timestamp).encode("utf-8")
    key = secret.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_signature(
    *, payload: str, timestamp: str, secret: str, signature: str
) -> bool:
    """Constant-time comparison. Returns True only on a byte-exact match."""
    expected = sign_request(payload=payload, timestamp=timestamp, secret=secret)
    return hmac.compare_digest(expected.encode("ascii"), signature.encode("ascii"))


__all__ = ["SigningError", "sign_request", "verify_signature"]
