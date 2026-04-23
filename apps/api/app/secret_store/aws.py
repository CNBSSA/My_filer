"""AWS Secrets Manager provider (prod target).

`boto3` is an **optional** dependency — it's installed in production
images but not pulled into local dev by default. If someone configures
`SECRETS_BACKEND=aws` without `boto3` installed, the factory raises a
clear error at startup rather than failing silently on the first lookup.

Secret name resolution:
  name `anthropic_api_key` with prefix `/mai-filer/prod/`
  -> `/mai-filer/prod/anthropic_api_key`

If the secret is absent, `.get()` returns None and the caller can fall
back to env. Transport / IAM failures raise `SecretsProviderError`.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.secret_store.base import SecretsProviderError

log = logging.getLogger("mai_filer.secrets.aws")


class AWSSecretsManagerProvider:
    """Looks up secrets under a shared prefix (e.g. `/mai-filer/prod/`)."""

    name = "aws"

    def __init__(
        self,
        *,
        prefix: str = "",
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = _make_client(region_name=region_name)
        # Normalize prefix so it always ends with exactly one `/`.
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""

    def get(self, key: str) -> str | None:
        if not key:
            return None
        secret_id = f"{self._prefix}{key.lower()}"
        try:
            response = self._client.get_secret_value(SecretId=secret_id)
        except Exception as exc:  # noqa: BLE001
            # Classify ResourceNotFoundException as "missing" (return None);
            # anything else is a provider error.
            if _is_not_found(exc):
                return None
            log.warning("AWS Secrets Manager lookup failed for %s: %s", secret_id, exc)
            raise SecretsProviderError(str(exc)) from exc

        value = response.get("SecretString")
        if value is None:
            # Binary-only secrets aren't how we store these; treat as missing.
            return None
        return value or None


def _is_not_found(exc: Exception) -> bool:
    """Tolerant check — works with either boto3 ClientError or stubs."""
    err = getattr(exc, "response", None)
    if isinstance(err, dict):
        code = (err.get("Error") or {}).get("Code")
        if code == "ResourceNotFoundException":
            return True
    name = exc.__class__.__name__
    return name == "ResourceNotFoundException"


@lru_cache(maxsize=1)
def _make_client(*, region_name: str | None = None) -> Any:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SecretsProviderError(
            "SECRETS_BACKEND=aws requires boto3. Install with "
            "`pip install 'boto3>=1.34'` (production images already ship it)."
        ) from exc
    return boto3.client("secretsmanager", region_name=region_name)
