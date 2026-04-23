"""OpenAI embeddings adapter (fallback vendor).

Activation: set `OPENAI_API_KEY` and either set
`EMBEDDINGS_PROVIDER=openai` explicitly, or leave Voyage unset so the
factory picks OpenAI automatically.

Optional dependency: `openai`.
"""

from __future__ import annotations

from app.memory.embeddings.base import EmbeddingResult, EmbeddingsError

DEFAULT_MODEL = "text-embedding-3-small"


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise EmbeddingsError("OpenAIProvider requires an api_key")
        self._api_key = api_key
        self.model = model
        self._client = None  # lazy

    def _ensure_client(self):  # type: ignore[no-untyped-def]
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise EmbeddingsError(
                "EMBEDDINGS_PROVIDER=openai requires the `openai` package. "
                "Install with `pip install openai` in the target environment."
            ) from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed(self, text: str) -> EmbeddingResult | None:
        if not text or not text.strip():
            return None
        client = self._ensure_client()
        try:
            response = client.embeddings.create(model=self.model, input=[text])
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingsError(f"openai embed failed: {exc}") from exc
        data = getattr(response, "data", None) or []
        if not data:
            return None
        vector = list(data[0].embedding)
        return EmbeddingResult(
            vector=vector, model=self.model, dimensions=len(vector)
        )
