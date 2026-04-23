"""Embeddings providers (P8.10).

Lets Mai Filer do semantic recall over the Learning Partner facts. Held
behind a small Protocol so swapping vendors is a factory flip:

  * `NoopProvider`   — no embeddings; callers fall back to KeywordRecall.
  * `VoyageProvider` — Anthropic's recommended vendor (voyage-3-lite by default).
  * `OpenAIProvider` — fallback if the owner prefers OpenAI.

Selection via `EMBEDDINGS_PROVIDER` env:
  - Explicit: `noop` | `voyage` | `openai`.
  - Auto (default): pick based on which API key env var is set.

Each adapter imports its vendor SDK lazily so dev / CI installs don't
drag unnecessary dependencies.
"""

from __future__ import annotations

from app.memory.embeddings.base import (
    EmbeddingResult,
    EmbeddingsError,
    EmbeddingsProvider,
)
from app.memory.embeddings.factory import (
    build_embeddings_provider,
    is_embeddings_enabled,
)
from app.memory.embeddings.noop import NoopProvider

__all__ = [
    "EmbeddingResult",
    "EmbeddingsError",
    "EmbeddingsProvider",
    "NoopProvider",
    "build_embeddings_provider",
    "is_embeddings_enabled",
]
