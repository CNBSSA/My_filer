"""Repositories — thin data-access helpers over the ORM.

Keeping data access out of the router means:
- The router stays small.
- Tests can substitute an in-memory SQLite without faking anything at the
  session level.
- Future async migration only touches this layer.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.mai_filer.schemas import ChatTurn
from app.db.models import Message, Thread


class ThreadRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_or_create(self, thread_id: str | None, *, language: str) -> Thread:
        if thread_id:
            thread = self._s.get(Thread, thread_id)
            if thread:
                return thread
        thread = Thread(id=thread_id, language=language) if thread_id else Thread(language=language)
        self._s.add(thread)
        self._s.flush()
        return thread

    def history_as_turns(self, thread_id: str) -> list[ChatTurn]:
        thread = self._s.get(Thread, thread_id)
        if not thread:
            return []
        return [
            ChatTurn(role=msg.role, content=msg.content)  # type: ignore[arg-type]
            for msg in thread.messages
            if msg.role in ("user", "assistant")
        ]


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add_user_message(self, *, thread_id: str, content: str, language: str) -> Message:
        message = Message(
            thread_id=thread_id,
            role="user",
            content=content,
            language=language,
        )
        self._s.add(message)
        self._s.flush()
        return message

    def add_assistant_message(
        self,
        *,
        thread_id: str,
        content: str,
        language: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> Message:
        message = Message(
            thread_id=thread_id,
            role="assistant",
            content=content,
            language=language,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )
        self._s.add(message)
        self._s.flush()
        return message
