"""NoopProvider — the default when no vendor is configured.

Returns `None` for every `embed()` call so callers know to skip the
embedding column and let `KeywordRecall` handle the query instead.
Keeps production installs zero-dependency until the owner picks a
real vendor.
"""

from __future__ import annotations

from app.memory.embeddings.base import EmbeddingResult


class NoopProvider:
    name = "noop"
    model = "noop"

    def embed(self, text: str) -> EmbeddingResult | None:  # noqa: ARG002
        return None
