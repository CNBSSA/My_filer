"""EmbeddingsProvider Protocol + shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EmbeddingsError(RuntimeError):
    """Raised when a provider can't compute an embedding for infrastructure
    reasons (network, auth, quota). Missing values are not errors."""


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    dimensions: int


class EmbeddingsProvider(Protocol):
    """Turns a short text (a YearlyFact label + value + meta) into a vector."""

    name: str
    model: str

    def embed(self, text: str) -> EmbeddingResult | None:
        """Return an embedding for `text`, or None if the provider is a noop
        or the input is empty. Raises `EmbeddingsError` on transport /
        auth / quota failures."""
