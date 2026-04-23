"""Secrets abstraction tests (P7.3)."""

from __future__ import annotations

from typing import Any

import pytest

from app.secrets import EnvSecretsProvider, SecretsProviderError
from app.secrets.aws import AWSSecretsManagerProvider
from app.secrets.factory import (
    build_secrets_provider,
    secret,
    set_default_provider,
)


# ---------------------------------------------------------------------------
# EnvSecretsProvider
# ---------------------------------------------------------------------------


def test_env_provider_returns_existing_value() -> None:
    p = EnvSecretsProvider(env={"ANTHROPIC_API_KEY": "abc"})
    assert p.get("anthropic_api_key") == "abc"
    assert p.get("ANTHROPIC_API_KEY") == "abc"


def test_env_provider_case_insensitive_fallback() -> None:
    p = EnvSecretsProvider(env={"mixedCase_Key": "val"})
    assert p.get("MIXEDCASE_KEY") == "val"


def test_env_provider_returns_none_when_missing() -> None:
    p = EnvSecretsProvider(env={})
    assert p.get("NOT_SET") is None


def test_env_provider_empty_value_is_none() -> None:
    p = EnvSecretsProvider(env={"X": ""})
    assert p.get("X") is None


# ---------------------------------------------------------------------------
# AWSSecretsManagerProvider
# ---------------------------------------------------------------------------


class FakeBoto:
    """Stub that mimics boto3's Secrets Manager client interface."""

    def __init__(self, *, secrets: dict[str, str]) -> None:
        self._secrets = secrets
        self.calls: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, Any]:  # noqa: N803
        self.calls.append(SecretId)
        if SecretId in self._secrets:
            return {"SecretString": self._secrets[SecretId]}
        err = type(
            "ResourceNotFoundException", (Exception,), {"response": {"Error": {"Code": "ResourceNotFoundException"}}}
        )
        raise err(f"not found: {SecretId}")


def test_aws_provider_returns_secret_string() -> None:
    stub = FakeBoto(
        secrets={"/mai-filer/prod/anthropic_api_key": "secret-from-sm"},
    )
    p = AWSSecretsManagerProvider(prefix="/mai-filer/prod/", client=stub)
    assert p.get("anthropic_api_key") == "secret-from-sm"
    assert stub.calls == ["/mai-filer/prod/anthropic_api_key"]


def test_aws_provider_lowercases_key() -> None:
    stub = FakeBoto(
        secrets={"/mai-filer/prod/nrs_client_secret": "sss"},
    )
    p = AWSSecretsManagerProvider(prefix="/mai-filer/prod/", client=stub)
    assert p.get("NRS_CLIENT_SECRET") == "sss"


def test_aws_provider_returns_none_when_not_found() -> None:
    stub = FakeBoto(secrets={})
    p = AWSSecretsManagerProvider(prefix="/mai-filer/prod/", client=stub)
    assert p.get("anything") is None


def test_aws_provider_escalates_unknown_errors() -> None:
    class BrokenClient:
        def get_secret_value(self, SecretId: str) -> Any:  # noqa: N803
            raise RuntimeError("IAM denied")

    p = AWSSecretsManagerProvider(prefix="/x/", client=BrokenClient())
    with pytest.raises(SecretsProviderError):
        p.get("anything")


# ---------------------------------------------------------------------------
# factory + secret() helper
# ---------------------------------------------------------------------------


def test_secret_falls_back_to_env_when_provider_is_missing(monkeypatch) -> None:
    class Missing:
        name = "aws"

        def get(self, key: str) -> str | None:
            return None

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-fallback")
    set_default_provider(Missing())
    try:
        assert secret("anthropic_api_key") == "env-fallback"
    finally:
        set_default_provider(None)


def test_secret_returns_provider_value_first(monkeypatch) -> None:
    class Fixed:
        name = "aws"

        def get(self, key: str) -> str | None:
            return "from-provider" if key == "anthropic_api_key" else None

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-fallback")
    set_default_provider(Fixed())
    try:
        assert secret("anthropic_api_key") == "from-provider"
    finally:
        set_default_provider(None)


def test_build_secrets_provider_rejects_unknown_backend(monkeypatch) -> None:
    set_default_provider(None)
    monkeypatch.setenv("SECRETS_BACKEND", "mystery")
    build_secrets_provider.cache_clear()
    with pytest.raises(SecretsProviderError):
        build_secrets_provider()
    monkeypatch.delenv("SECRETS_BACKEND", raising=False)
    build_secrets_provider.cache_clear()
