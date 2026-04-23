"""Secrets abstraction (P7.3).

Production reads credentials from AWS Secrets Manager (or the Nigerian
KMS partner); dev reads from `.env`. Everything in between is an env-
var-compatible dict so the rest of the app never changes shape.

Backends are chosen by `SECRETS_BACKEND`:
  - `env`  (default) — `EnvSecretsProvider`; passthrough `os.environ`.
  - `aws`  — `AWSSecretsManagerProvider`; needs `boto3` installed and
             `SECRETS_PATH_PREFIX` pointing at the secret namespace
             (e.g. `/mai-filer/prod/`).

The Protocol is intentionally small: `.get(name) -> str | None`. Callers
wrap the value as needed; there is no get-many fan-out because AWS
charges per GetSecretValue call and we want every lookup to be
explicit.
"""

from __future__ import annotations

from app.secret_store.base import SecretsProvider, SecretsProviderError
from app.secret_store.env import EnvSecretsProvider
from app.secret_store.factory import build_secrets_provider, secret

__all__ = [
    "EnvSecretsProvider",
    "SecretsProvider",
    "SecretsProviderError",
    "build_secrets_provider",
    "secret",
]
