"""Provider selection + the top-level `secret()` helper."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from app.secret_store.aws import AWSSecretsManagerProvider
from app.secret_store.base import SecretsProvider, SecretsProviderError
from app.secret_store.env import EnvSecretsProvider

log = logging.getLogger("mai_filer.secrets")


_OVERRIDE: SecretsProvider | None = None


def set_default_provider(provider: SecretsProvider | None) -> None:
    """Test hook — inject a provider without poking environment variables."""
    global _OVERRIDE
    _OVERRIDE = provider
    build_secrets_provider.cache_clear()
    secret.cache_clear()


@lru_cache(maxsize=1)
def build_secrets_provider() -> SecretsProvider:
    """Pick a provider per `SECRETS_BACKEND`. Defaults to env."""
    if _OVERRIDE is not None:
        return _OVERRIDE
    backend = (os.environ.get("SECRETS_BACKEND") or "env").lower()
    if backend == "env":
        return EnvSecretsProvider()
    if backend == "aws":
        prefix = os.environ.get("SECRETS_PATH_PREFIX", "")
        region = os.environ.get("AWS_REGION")
        return AWSSecretsManagerProvider(prefix=prefix, region_name=region)
    raise SecretsProviderError(
        f"unknown SECRETS_BACKEND: {backend!r} (expected 'env' or 'aws')"
    )


@lru_cache(maxsize=256)
def secret(key: str, *, fallback_env: bool = True) -> str | None:
    """Fetch one secret with a controlled fallback to env.

    The cache is small and process-local: secrets rotate on deploy so
    "cache until process restart" is the right TTL.
    """
    provider = build_secrets_provider()
    value = provider.get(key)
    if value is not None:
        return value
    if fallback_env and provider.name != "env":
        # Fall through to env so partial migrations work (e.g. NRS creds in
        # Secrets Manager, DOJAH_API_KEY still in an env var).
        return EnvSecretsProvider().get(key)
    return None
