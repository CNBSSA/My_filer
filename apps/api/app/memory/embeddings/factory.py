"""Pick an EmbeddingsProvider per env flag (or auto-detect)."""

from __future__ import annotations

import os
from functools import lru_cache

from app.memory.embeddings.base import EmbeddingsProvider
from app.memory.embeddings.noop import NoopProvider
from app.memory.embeddings.openai import OpenAIProvider
from app.memory.embeddings.voyage import VoyageProvider


_OVERRIDE: EmbeddingsProvider | None = None


def set_default_provider(provider: EmbeddingsProvider | None) -> None:
    """Test hook — inject a provider bypassing env detection."""
    global _OVERRIDE
    _OVERRIDE = provider
    build_embeddings_provider.cache_clear()


@lru_cache(maxsize=1)
def build_embeddings_provider() -> EmbeddingsProvider:
    """Select based on EMBEDDINGS_PROVIDER, or auto-detect from API keys."""
    if _OVERRIDE is not None:
        return _OVERRIDE

    explicit = (os.environ.get("EMBEDDINGS_PROVIDER") or "").strip().lower()
    voyage_key = os.environ.get("VOYAGE_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if explicit == "noop":
        return NoopProvider()
    if explicit == "voyage":
        return VoyageProvider(api_key=voyage_key)
    if explicit == "openai":
        return OpenAIProvider(api_key=openai_key)

    # Auto-detect: Voyage first (Anthropic's recommendation), then OpenAI,
    # else Noop so the rest of the app degrades gracefully to KeywordRecall.
    if voyage_key:
        return VoyageProvider(api_key=voyage_key)
    if openai_key:
        return OpenAIProvider(api_key=openai_key)
    return NoopProvider()


def is_embeddings_enabled() -> bool:
    """True when the active provider returns real embeddings."""
    return build_embeddings_provider().name != "noop"
