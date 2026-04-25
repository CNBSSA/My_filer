"""API key authentication for Mai Filer.

Provides a FastAPI dependency that requires a Bearer token matching
the API_TOKEN environment variable. Used to protect all PII-bearing
endpoints.

If API_TOKEN is not set the middleware refuses all requests (fail-closed).
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def require_api_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency: raise 401 if the Bearer token does not match API_TOKEN.

    Fail-closed: if the env var is not set, every request is rejected with 401
    (not 503 — the misconfiguration is an auth failure, not a service failure).
    Uses `secrets.compare_digest` to avoid timing-oracle leaks.
    Logs every failure with the correlation ID for intrusion detection.
    """
    correlation_id = getattr(request.state, "correlation_id", "-")
    expected = os.environ.get("API_TOKEN", "")
    if not expected:
        log.warning(
            "Auth failure: API_TOKEN not configured",
            extra={"correlation_id": correlation_id, "path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication is not configured.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        log.warning(
            "Auth failure: invalid or missing Bearer token",
            extra={"correlation_id": correlation_id, "path": request.url.path},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
