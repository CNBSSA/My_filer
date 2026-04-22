"""Mai Filer orchestrator — Claude client wrapper.

Responsibilities:
- Build the system prompt with prompt caching on the base doctrine block.
- Layer the user's language addendum on top.
- Sync chat: single non-streaming call, with an internal tool-use loop that
  invokes local tools (PIT / PAYE / VAT / reliefs) until Claude stops.
- Async streaming chat: yields SSE-ready chunks (token deltas + final usage).

Phase 2 (P2.7/P2.8) introduced tool use on the sync path. Streaming tool use
is a future enhancement; streaming currently runs without tools so UI demos
stay simple.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic import Anthropic

from app.agents.mai_filer.prompt import build_system_blocks
from app.agents.mai_filer.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
)
from app.agents.mai_filer.tools import run_tool, tool_schemas
from app.config import get_settings
from app.i18n import get_language
from app.i18n.drift import apply_drift_note


MAX_TOOL_TURNS = 5  # safety cap on the tool-use loop


@dataclass
class AnthropicUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class StreamResult:
    text: str
    usage: AnthropicUsage


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class AgentTurn:
    """One round-trip with Claude.

    - `text`: any text blocks emitted this turn (may be empty mid-loop).
    - `tool_calls`: tool_use blocks Claude wants us to execute.
    - `stop_reason`: "tool_use" → continue the loop; "end_turn" → we're done.
    - `usage`: accumulated tokens this turn.
    """

    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: AnthropicUsage


class AnthropicClient(Protocol):
    """Test-friendly surface; RealAnthropicClient wraps the SDK."""

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AgentTurn:
        ...

    def messages_stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> Iterator[str | StreamResult]:
        ...


class RealAnthropicClient:
    """Adapter around the Anthropic SDK."""

    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AgentTurn:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        response = self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        input=dict(block.input),
                    )
                )

        usage = AnthropicUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(
                response.usage, "cache_creation_input_tokens", 0
            )
            or 0,
        )
        return AgentTurn(
            text="".join(text_parts).strip(),
            tool_calls=tool_calls,
            stop_reason=getattr(response, "stop_reason", "end_turn") or "end_turn",
            usage=usage,
        )

    def messages_stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> Iterator[str | StreamResult]:
        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            for text_delta in stream.text_stream:
                yield text_delta
            final_message = stream.get_final_message()
            text_parts = [
                block.text
                for block in final_message.content
                if getattr(block, "type", None) == "text"
            ]
            text = "".join(text_parts).strip()
            usage = AnthropicUsage(
                input_tokens=getattr(final_message.usage, "input_tokens", 0) or 0,
                output_tokens=getattr(final_message.usage, "output_tokens", 0) or 0,
                cache_read_input_tokens=getattr(
                    final_message.usage, "cache_read_input_tokens", 0
                )
                or 0,
                cache_creation_input_tokens=getattr(
                    final_message.usage, "cache_creation_input_tokens", 0
                )
                or 0,
            )
            yield StreamResult(text=text, usage=usage)


class MaiFilerOrchestrator:
    def __init__(
        self,
        client: AnthropicClient,
        model: str,
        max_tokens: int = 1024,
        enable_tools: bool = True,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._enable_tools = enable_tools

    def _build_messages(self, request: ChatRequest) -> list[dict]:
        messages: list[dict] = [
            {"role": turn.role, "content": turn.content} for turn in request.history
        ]
        messages.append({"role": "user", "content": request.message})
        return messages

    def _tools(self) -> list[dict] | None:
        return tool_schemas() if self._enable_tools else None

    def chat(self, request: ChatRequest) -> ChatResponse:
        language = get_language(request.language)
        system_blocks = build_system_blocks(language.code)
        messages = self._build_messages(request)

        tools = self._tools()
        accumulated_text = ""
        total_usage = AnthropicUsage()
        turns_taken = 0

        while True:
            turn = self._client.messages_create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_blocks,
                messages=messages,
                tools=tools,
            )
            total_usage.input_tokens += turn.usage.input_tokens
            total_usage.output_tokens += turn.usage.output_tokens
            total_usage.cache_read_input_tokens += turn.usage.cache_read_input_tokens
            total_usage.cache_creation_input_tokens += turn.usage.cache_creation_input_tokens

            if turn.text:
                accumulated_text = turn.text

            if turn.stop_reason != "tool_use" or not turn.tool_calls:
                break

            # Append the assistant's tool-use turn verbatim (text + tool_use blocks).
            assistant_blocks: list[dict[str, Any]] = []
            if turn.text:
                assistant_blocks.append({"type": "text", "text": turn.text})
            for call in turn.tool_calls:
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.input,
                    }
                )
            messages.append({"role": "assistant", "content": assistant_blocks})

            # Execute each tool and feed results back as a single user turn.
            tool_results: list[dict[str, Any]] = []
            for call in turn.tool_calls:
                result_json = run_tool(call.name, call.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": result_json,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

            turns_taken += 1
            if turns_taken >= MAX_TOOL_TURNS:
                break

        final_text = apply_drift_note(accumulated_text, language.code)

        return ChatResponse(
            thread_id=request.thread_id or str(uuid.uuid4()),
            message=final_text,
            language=language.code,
            model=self._model,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            cache_read_tokens=total_usage.cache_read_input_tokens,
            cache_creation_tokens=total_usage.cache_creation_input_tokens,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        language = get_language(request.language)
        system_blocks = build_system_blocks(language.code)
        thread_id = request.thread_id or str(uuid.uuid4())

        yield ChatStreamChunk(
            event="start",
            thread_id=thread_id,
            language=language.code,
            model=self._model,
        )

        final: StreamResult | None = None
        for item in self._client.messages_stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_blocks,
            messages=self._build_messages(request),
        ):
            if isinstance(item, StreamResult):
                final = item
            else:
                yield ChatStreamChunk(event="delta", thread_id=thread_id, delta=item)

        if final is None:
            final = StreamResult(text="", usage=AnthropicUsage())

        final_text = apply_drift_note(final.text, language.code)

        yield ChatStreamChunk(
            event="done",
            thread_id=thread_id,
            language=language.code,
            model=self._model,
            message=final_text,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            cache_read_tokens=final.usage.cache_read_input_tokens,
            cache_creation_tokens=final.usage.cache_creation_input_tokens,
        )


def build_default_orchestrator() -> MaiFilerOrchestrator:
    settings = get_settings()
    client: AnthropicClient = RealAnthropicClient(api_key=settings.anthropic_api_key)
    return MaiFilerOrchestrator(
        client=client,
        model=settings.claude_model_orchestrator,
    )


__all__ = [
    "AgentTurn",
    "AnthropicClient",
    "AnthropicUsage",
    "MaiFilerOrchestrator",
    "RealAnthropicClient",
    "StreamResult",
    "ToolCall",
    "build_default_orchestrator",
]
