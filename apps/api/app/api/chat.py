"""Chat router.

- P1.5 non-streaming chat
- P1.7 SSE streaming
- P1.9 persistence: user turn saved before Claude, assistant turn after
- P1.11 language list
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.mai_filer.orchestrator import (
    MaiFilerOrchestrator,
    build_default_orchestrator,
)
from app.agents.mai_filer.schemas import ChatRequest, ChatResponse, LanguageInfo
from app.db.repositories import MessageRepository, ThreadRepository
from app.db.session import get_session
from app.i18n import get_language, list_supported

router = APIRouter(prefix="/v1", tags=["chat"])


def get_orchestrator() -> MaiFilerOrchestrator:
    """Dependency provider so tests can override with a mock."""
    return build_default_orchestrator()


@router.get("/languages", response_model=list[LanguageInfo])
async def languages() -> list[dict[str, str]]:
    """Supported languages for the chat UI selector (ADR-0004)."""
    return list_supported()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: MaiFilerOrchestrator = Depends(get_orchestrator),
    session: Session = Depends(get_session),
) -> ChatResponse:
    """Single-turn Mai Filer chat.

    - Resolves / creates a thread.
    - Loads stored history (overrides any `history` in the request body, which
      is only a fallback for stateless callers).
    - Persists the user turn, calls Claude, persists the assistant turn.
    """
    language = get_language(request.language)
    threads = ThreadRepository(session)
    messages = MessageRepository(session)

    thread = threads.get_or_create(request.thread_id, language=language.code)

    stored_history = threads.history_as_turns(thread.id)
    merged_history = stored_history if stored_history else request.history

    messages.add_user_message(thread_id=thread.id, content=request.message, language=language.code)

    orch_request = ChatRequest(
        message=request.message,
        language=language.code,
        thread_id=thread.id,
        history=merged_history,
    )
    response = orchestrator.chat(orch_request)

    messages.add_assistant_message(
        thread_id=thread.id,
        content=response.message,
        language=response.language,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cache_read_tokens=response.cache_read_tokens,
        cache_creation_tokens=response.cache_creation_tokens,
    )
    session.commit()
    return response.model_copy(update={"thread_id": thread.id})


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    orchestrator: MaiFilerOrchestrator = Depends(get_orchestrator),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Server-Sent Events stream of Mai Filer tokens.

    Frames:
      event: start|delta|done
      data: {json ChatStreamChunk}

    Persists the user turn before streaming; persists the assistant turn on
    `done`. If the connection drops mid-stream, the DB is left with only the
    user turn — intentional, since Phase 1b is expected to add resumption.
    """
    language = get_language(request.language)
    threads = ThreadRepository(session)
    messages = MessageRepository(session)

    thread = threads.get_or_create(request.thread_id, language=language.code)

    stored_history = threads.history_as_turns(thread.id)
    merged_history = stored_history if stored_history else request.history

    messages.add_user_message(thread_id=thread.id, content=request.message, language=language.code)
    session.commit()

    orch_request = ChatRequest(
        message=request.message,
        language=language.code,
        thread_id=thread.id,
        history=merged_history,
    )

    async def sse_source() -> AsyncIterator[bytes]:
        async for chunk in orchestrator.stream_chat(orch_request):
            payload = chunk.model_dump_json()
            frame = f"event: {chunk.event}\ndata: {payload}\n\n"
            yield frame.encode("utf-8")

            if chunk.event == "done":
                data = json.loads(payload)
                messages.add_assistant_message(
                    thread_id=thread.id,
                    content=data.get("message") or "",
                    language=data.get("language") or language.code,
                    model=data.get("model") or "",
                    input_tokens=data.get("input_tokens", 0),
                    output_tokens=data.get("output_tokens", 0),
                    cache_read_tokens=data.get("cache_read_tokens", 0),
                    cache_creation_tokens=data.get("cache_creation_tokens", 0),
                )
                session.commit()

    return StreamingResponse(
        sse_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
