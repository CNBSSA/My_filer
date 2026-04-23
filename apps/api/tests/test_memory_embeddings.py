"""Embeddings provider + factory tests (P8.10)."""

from __future__ import annotations

import pytest

from app.memory.embeddings import (
    EmbeddingResult,
    NoopProvider,
    build_embeddings_provider,
    is_embeddings_enabled,
)
from app.memory.embeddings.factory import set_default_provider


def test_noop_provider_returns_none() -> None:
    p = NoopProvider()
    assert p.embed("anything") is None
    assert p.name == "noop"


def test_factory_defaults_to_noop_when_no_keys(monkeypatch) -> None:
    set_default_provider(None)
    for var in ("EMBEDDINGS_PROVIDER", "VOYAGE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    build_embeddings_provider.cache_clear()
    provider = build_embeddings_provider()
    assert provider.name == "noop"
    assert is_embeddings_enabled() is False


def test_factory_auto_selects_voyage_when_key_present(monkeypatch) -> None:
    set_default_provider(None)
    monkeypatch.setenv("VOYAGE_API_KEY", "sk-voyage-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDINGS_PROVIDER", raising=False)
    build_embeddings_provider.cache_clear()
    provider = build_embeddings_provider()
    assert provider.name == "voyage"
    build_embeddings_provider.cache_clear()


def test_factory_auto_falls_through_to_openai(monkeypatch) -> None:
    set_default_provider(None)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.delenv("EMBEDDINGS_PROVIDER", raising=False)
    build_embeddings_provider.cache_clear()
    provider = build_embeddings_provider()
    assert provider.name == "openai"
    build_embeddings_provider.cache_clear()


def test_explicit_noop_overrides_auto_detect(monkeypatch) -> None:
    set_default_provider(None)
    monkeypatch.setenv("VOYAGE_API_KEY", "sk-voyage-test")
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "noop")
    build_embeddings_provider.cache_clear()
    provider = build_embeddings_provider()
    assert provider.name == "noop"
    build_embeddings_provider.cache_clear()


def test_set_default_provider_overrides_everything() -> None:
    class Fake:
        name = "fake"
        model = "fake-1"

        def embed(self, text: str) -> EmbeddingResult | None:
            return EmbeddingResult(vector=[1.0, 2.0, 3.0], model=self.model, dimensions=3)

    set_default_provider(Fake())
    try:
        assert build_embeddings_provider().name == "fake"
        assert is_embeddings_enabled() is True
    finally:
        set_default_provider(None)
        build_embeddings_provider.cache_clear()
