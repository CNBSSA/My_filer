"""SecretsProvider Protocol + shared error type."""

from __future__ import annotations

from typing import Protocol


class SecretsProviderError(RuntimeError):
    """Raised when a provider cannot fetch a secret for infrastructure reasons
    (network, auth, misconfiguration). Missing values are NOT errors — they
    return None so callers can fall back to env."""


class SecretsProvider(Protocol):
    """Read-only access to named secrets.

    Returns None when the secret is simply absent. Raises
    `SecretsProviderError` when the provider itself is unhealthy.
    """

    name: str

    def get(self, key: str) -> str | None: ...
