"""NRS JWT signer (P7.4 prep).

The HMAC-SHA256 handshake (`gateway/signing.py`) is the 2026 NRS contract.
Post-Rev360 cutover, NRS may migrate to JWT bearer tokens; this module
is ready for that swap so the rest of the gateway doesn't move.

Tokens carry the canonical claims:

    iss     issuer (`JWT_ISSUER`)
    sub     `business_id`
    aud     NRS base URL
    iat     now (epoch seconds)
    exp     now + `DEFAULT_TTL_SECONDS`
    jti     random uuid (replay protection)
    sha256  hex SHA-256 digest of the payload body

The `sha256` claim binds the JWT to the exact payload — if an attacker
intercepts the token, they can't point it at a different body.

Algorithm default: HS256 (owner supplies a shared secret). RS256 + a
PEM private key is supported by simply flipping `JWT_ALGORITHM=RS256`
and dropping the key into `NRS_JWT_PRIVATE_KEY`.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

import jwt  # PyJWT

DEFAULT_TTL_SECONDS = 300  # 5 minutes


class JWTSigningError(ValueError):
    """Raised when we cannot produce a token (missing key, bad algorithm)."""


def sign_jwt(
    *,
    payload: str,
    business_id: str,
    issuer: str,
    audience: str,
    secret_or_private_key: str,
    algorithm: str = "HS256",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: float | None = None,
) -> str:
    """Return a JWT binding `payload` to the issuer + business_id + audience.

    `payload` is the same canonical body that would otherwise be HMAC-signed.
    We attach its SHA-256 as the `sha256` claim so the receiver can verify
    body integrity without trusting transport.
    """
    if not secret_or_private_key:
        raise JWTSigningError("JWT signing key is empty — refusing to sign")
    if not business_id or not issuer or not audience:
        raise JWTSigningError("business_id / issuer / audience must be non-empty")

    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + ttl_seconds
    body_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    claims: dict[str, Any] = {
        "iss": issuer,
        "sub": business_id,
        "aud": audience,
        "iat": issued_at,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
        "sha256": body_sha,
    }
    try:
        token = jwt.encode(claims, secret_or_private_key, algorithm=algorithm)
    except Exception as exc:  # PyJWT raises its own exception hierarchy
        raise JWTSigningError(f"JWT encode failed: {exc}") from exc
    # PyJWT < 2 returned bytes; 2+ returns str. Normalize.
    return token if isinstance(token, str) else token.decode("ascii")


def verify_jwt(
    *,
    token: str,
    payload: str,
    issuer: str,
    audience: str,
    secret_or_public_key: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    """Verify token signature, issuer, audience, expiry, and payload sha256
    binding. Returns the parsed claims on success; raises `JWTSigningError`
    with a plain-language reason on any failure."""
    algorithms = algorithms or ["HS256"]
    try:
        claims = jwt.decode(
            token,
            secret_or_public_key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise JWTSigningError("token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise JWTSigningError("audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise JWTSigningError("issuer mismatch") from exc
    except jwt.InvalidTokenError as exc:
        raise JWTSigningError(f"invalid token: {exc}") from exc

    body_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if claims.get("sha256") != body_sha:
        raise JWTSigningError("payload sha256 does not match token claim")
    return claims


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "JWTSigningError",
    "sign_jwt",
    "verify_jwt",
]
