"""Voyage AI embeddings adapter (Anthropic's recommended vendor).

Optional dependency: `voyageai`. Install only in environments where
embeddings are enabled — dev and CI work without it via the Noop
provider.

Activation: set `VOYAGE_API_KEY` in the environment. The factory will
auto-select this provider when that key is present and no explicit
`EMBEDDINGS_PROVIDER` override is set.
"""

from __future__ import annotations

from app.memory.embeddings.base import EmbeddingResult, EmbeddingsError

DEFAULT_MODEL = "voyage-3-lite"


class VoyageProvider:
    name = "voyage"

    def __init__(self, *, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise EmbeddingsError("VoyageProvider requires an api_key")
        self._api_key = api_key
        self.model = model
        self._client = None  # lazy

    def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._client is not None:
            return self._client
        try:
            import voyageai  # type: ignore[import-not-found]
        except ImportError as exc:
            raise EmbeddingsError(
                "EMBEDDINGS_PROVIDER=voyage requires the `voyageai` package. "
                "Install with `pip install voyageai` in the target environment."
            ) from exc
        self._client = voyageai.Client(api_key=self._api_key)
        return self._client

    def embed(self, text: str) -> EmbeddingResult | None:
        if not text or not text.strip():
            return None
        client = self._ensure_client()
        try:
            response = client.embed([text], model=self.model, input_type="document")
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingsError(f"voyage embed failed: {exc}") from exc
        vectors = getattr(response, "embeddings", None) or []
        if not vectors:
            return None
        vector = list(vectors[0])
        return EmbeddingResult(
            vector=vector, model=self.model, dimensions=len(vector)
        )
