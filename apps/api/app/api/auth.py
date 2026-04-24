"""API key authentication for Mai Filer.

Provides a FastAPI dependency that requires a Bearer token matching
the API_TOKEN environment variable. Used to protect all PII-bearing
endpoints.

If API_TOKEN is not set the middleware refuses all requests (fail-closed).
"""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency: raise 401 if the Bearer token does not match API_TOKEN.

    Fail-closed: if the env var is not set, every request is rejected.
    Uses `secrets.compare_digest` to avoid timing-oracle leaks.
    """
    expected = os.environ.get("API_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API authentication is not configured. "
                "Set the API_TOKEN environment variable."
            ),
        )
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
