"""Pydantic request / response schemas for the Mai Filer chat API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant"]


class ChatTurn(BaseModel):
    """A single turn in a chat thread."""

    role: Role
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    """Incoming chat request.

    `language` selects a Mai Filer speaking voice from the i18n registry.
    `thread_id` is optional; when omitted a new thread is created server-side
    in Phase 1b. For the first P1.5 slice, the server is stateless and just
    echoes prior turns passed explicitly in `history`.
    """

    message: str = Field(min_length=1, max_length=20_000)
    language: str = Field(default="en")
    thread_id: str | None = None
    history: list[ChatTurn] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Outgoing chat response."""

    thread_id: str
    message: str
    language: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class LanguageInfo(BaseModel):
    code: str
    label: str
    english: str


StreamEvent = Literal["start", "delta", "done"]


class ChatStreamChunk(BaseModel):
    """One SSE frame. `delta` carries incremental text; `done` carries final
    message + usage. `start` announces the thread_id so clients can bind UI
    state before the first token arrives."""

    event: StreamEvent
    thread_id: str
    delta: str | None = None
    message: str | None = None
    language: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
