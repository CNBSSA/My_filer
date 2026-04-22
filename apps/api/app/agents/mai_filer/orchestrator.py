"""Mai Filer orchestrator — Claude client wrapper.

Responsible for:
- Building the system prompt with prompt caching on the base doctrine block.
- Layering the user's language addendum on top.
- Sending a single chat turn and returning the text + usage.

Phase 1 keeps this single-turn and stateless; Phase 1b adds DB-backed thread
persistence and Phase 2 introduces tool use.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from anthropic import Anthropic

from app.agents.mai_filer.prompt import build_system_blocks
from app.agents.mai_filer.schemas import ChatRequest, ChatResponse
from app.config import get_settings
from app.i18n import get_language


@dataclass
class AnthropicUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class AnthropicClient(Protocol):
    """Minimal protocol so tests can inject a fake without importing anthropic."""

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> tuple[str, AnthropicUsage]:
        ...


class RealAnthropicClient:
    """Thin adapter over the Anthropic SDK; exposes the Protocol above."""

    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> tuple[str, AnthropicUsage]:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text_parts = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        text = "".join(text_parts).strip()
        usage = AnthropicUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(
                response.usage, "cache_creation_input_tokens", 0
            )
            or 0,
        )
        return text, usage


class MaiFilerOrchestrator:
    """Thin orchestrator — builds the request, delegates to Claude, returns a
    typed response. No business logic lives here; tool dispatch arrives in
    Phase 2 (P2.7+)."""

    def __init__(self, client: AnthropicClient, model: str, max_tokens: int = 1024) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def chat(self, request: ChatRequest) -> ChatResponse:
        language = get_language(request.language)
        system_blocks = build_system_blocks(language.code)

        messages: list[dict] = [
            {"role": turn.role, "content": turn.content} for turn in request.history
        ]
        messages.append({"role": "user", "content": request.message})

        text, usage = self._client.messages_create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_blocks,
            messages=messages,
        )

        return ChatResponse(
            thread_id=request.thread_id or str(uuid.uuid4()),
            message=text,
            language=language.code,
            model=self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_input_tokens,
            cache_creation_tokens=usage.cache_creation_input_tokens,
        )


def build_default_orchestrator() -> MaiFilerOrchestrator:
    """Factory using the live Anthropic client and settings."""
    settings = get_settings()
    client: AnthropicClient = RealAnthropicClient(api_key=settings.anthropic_api_key)
    return MaiFilerOrchestrator(
        client=client,
        model=settings.claude_model_orchestrator,
    )
