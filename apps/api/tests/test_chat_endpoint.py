"""Chat endpoint tests with a mocked orchestrator (P1.6, P1.7, P1.9)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agents.mai_filer.orchestrator import (
    AgentTurn,
    AnthropicUsage,
    MaiFilerOrchestrator,
    StreamResult,
)
from app.agents.mai_filer.schemas import ChatResponse
from app.api.chat import get_orchestrator
from app.db.models import Message, Thread
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


class FakeAnthropic:
    """Record calls and return a deterministic response (sync + stream)."""

    def __init__(
        self,
        reply: str = "Hello, I'm Mai Filer.",
        stream_deltas: list[str] | None = None,
    ) -> None:
        self.reply = reply
        self.stream_deltas = stream_deltas or ["Hello, ", "I'm ", "Mai Filer."]
        self.calls: list[dict] = []
        self.stream_calls: list[dict] = []

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AgentTurn:
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
                "tools": tools,
            }
        )
        return AgentTurn(
            text=self.reply,
            tool_calls=[],
            stop_reason="end_turn",
            usage=AnthropicUsage(
                input_tokens=100,
                output_tokens=42,
                cache_read_input_tokens=80,
                cache_creation_input_tokens=0,
            ),
        )

    def messages_stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> Iterator[str | StreamResult]:
        self.stream_calls.append(
            {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
        )
        for delta in self.stream_deltas:
            yield delta
        yield StreamResult(
            text="".join(self.stream_deltas),
            usage=AnthropicUsage(
                input_tokens=120,
                output_tokens=58,
                cache_read_input_tokens=100,
                cache_creation_input_tokens=0,
            ),
        )


def _orchestrator_with_fake(fake: FakeAnthropic) -> MaiFilerOrchestrator:
    return MaiFilerOrchestrator(client=fake, model="claude-opus-4-7", max_tokens=512)


def test_chat_returns_assistant_reply() -> None:
    fake = FakeAnthropic(reply="Welcome! I can help with your 2026 PIT filing.")
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/chat",
            json={"message": "Hello Mai", "language": "en"},
        )
        assert response.status_code == 200
        body = ChatResponse.model_validate(response.json())
        assert body.message.startswith("Welcome!")
        assert body.language == "en"
        assert body.model == "claude-opus-4-7"
        assert body.cache_read_tokens == 80
        call = fake.calls[0]
        assert len(call["system"]) == 2
        assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert call["messages"][-1] == {"role": "user", "content": "Hello Mai"}
    finally:
        app.dependency_overrides.clear()


def test_chat_routes_language_to_orchestrator() -> None:
    fake = FakeAnthropic(reply="Sannu!")
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/chat",
            json={"message": "Barka da zuwa", "language": "ha"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["language"] == "ha"
        lang_block = fake.calls[0]["system"][1]["text"]
        assert "Hausa" in lang_block
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)
    response = client.post("/v1/chat", json={"message": "", "language": "en"})
    assert response.status_code == 422


def test_languages_endpoint_lists_v1_set() -> None:
    client = TestClient(app)
    response = client.get("/v1/languages")
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert codes == {"en", "ha", "yo", "ig", "pcm"}


def _parse_sse(text: str) -> list[dict]:
    frames: list[dict] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        frame: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                frame["event"] = line[len("event:") :].strip()
            elif line.startswith("data:"):
                frame["data"] = json.loads(line[len("data:") :].strip())
        frames.append(frame)
    return frames


def test_chat_stream_emits_start_delta_done() -> None:
    fake = FakeAnthropic(stream_deltas=["Hello, ", "I am ", "Mai Filer."])
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        with client.stream(
            "POST", "/v1/chat/stream", json={"message": "Hi", "language": "en"}
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join(chunk for chunk in response.iter_text())
        frames = _parse_sse(body)
        events = [f["event"] for f in frames]
        assert events[0] == "start"
        assert events[-1] == "done"
        assert events.count("delta") == 3
        assembled = "".join(f["data"]["delta"] for f in frames if f["event"] == "delta")
        assert assembled == "Hello, I am Mai Filer."
        done = frames[-1]["data"]
        assert done["message"] == "Hello, I am Mai Filer."
        assert done["language"] == "en"
        assert done["output_tokens"] == 58
        assert done["cache_read_tokens"] == 100
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_routes_language() -> None:
    fake = FakeAnthropic(stream_deltas=["Sannu!"])
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        with client.stream(
            "POST", "/v1/chat/stream", json={"message": "Barka", "language": "ha"}
        ) as response:
            body = "".join(chunk for chunk in response.iter_text())
        frames = _parse_sse(body)
        done = frames[-1]["data"]
        assert done["language"] == "ha"
        assert "Hausa" in fake.stream_calls[0]["system"][1]["text"]
    finally:
        app.dependency_overrides.clear()


def test_chat_uses_request_history_on_first_turn() -> None:
    """When a request carries explicit history and the thread is new, the
    orchestrator receives that history verbatim."""
    fake = FakeAnthropic(reply="Got it.")
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/chat",
            json={
                "message": "What is my tax?",
                "language": "en",
                "history": [
                    {"role": "user", "content": "Hi Mai"},
                    {"role": "assistant", "content": "Hello! What's your income?"},
                ],
            },
        )
        assert response.status_code == 200
        messages = fake.calls[0]["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert messages[-1]["content"] == "What is my tax?"
    finally:
        app.dependency_overrides.clear()


def test_chat_persists_turns_and_returns_thread_id(db_session) -> None:
    """P1.9 — user + assistant turns land in the DB."""
    fake = FakeAnthropic(reply="Welcome to Mai Filer.")
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/chat", json={"message": "Hello", "language": "en"}
        )
        assert response.status_code == 200
        thread_id = response.json()["thread_id"]
        thread = db_session.get(Thread, thread_id)
        assert thread is not None
        assert thread.language == "en"
        msgs = thread.messages
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[0].content == "Hello"
        assert msgs[1].content == "Welcome to Mai Filer."
        assert msgs[1].model == "claude-opus-4-7"
        assert msgs[1].cache_read_tokens == 80
    finally:
        app.dependency_overrides.clear()


def test_chat_loads_prior_turns_from_db_on_second_call(db_session) -> None:
    """Second call on the same thread: stored history is passed to the model,
    not the (untrusted) request.history."""
    fake = FakeAnthropic(reply="Your PIT is ₦450,000.")
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        first = client.post(
            "/v1/chat", json={"message": "I earn ₦5m", "language": "en"}
        )
        thread_id = first.json()["thread_id"]

        second = client.post(
            "/v1/chat",
            json={"message": "What is my PIT?", "language": "en", "thread_id": thread_id},
        )
        assert second.status_code == 200
        # Second Claude call should see: prior user + prior assistant + new user.
        messages = fake.calls[1]["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert messages[0]["content"] == "I earn ₦5m"
        assert messages[2]["content"] == "What is my PIT?"

        thread = db_session.get(Thread, thread_id)
        assert len(thread.messages) == 4
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_persists_assistant_turn_on_done(db_session) -> None:
    fake = FakeAnthropic(stream_deltas=["Hello ", "Mai."])
    app.dependency_overrides[get_orchestrator] = lambda: _orchestrator_with_fake(fake)
    try:
        client = TestClient(app)
        with client.stream(
            "POST", "/v1/chat/stream", json={"message": "Hi", "language": "yo"}
        ) as response:
            body = "".join(chunk for chunk in response.iter_text())
        frames = _parse_sse(body)
        thread_id = frames[0]["data"]["thread_id"]
        # Count messages in the DB.
        persisted = (
            db_session.query(Message).filter(Message.thread_id == thread_id).all()
        )
        roles = sorted(m.role for m in persisted)
        assert roles == ["assistant", "user"]
        assistant = next(m for m in persisted if m.role == "assistant")
        assert assistant.content == "Hello Mai."
        assert assistant.language == "yo"
    finally:
        app.dependency_overrides.clear()
