"""Chat endpoint tests with a mocked orchestrator (P1.6)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents.mai_filer.orchestrator import AnthropicUsage, MaiFilerOrchestrator
from app.agents.mai_filer.schemas import ChatResponse
from app.api.chat import get_orchestrator
from app.main import app


class FakeAnthropic:
    """Record calls and return a deterministic response."""

    def __init__(self, reply: str = "Hello, I'm Mai Filer.") -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
    ) -> tuple[str, AnthropicUsage]:
        self.calls.append(
            {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
        )
        return self.reply, AnthropicUsage(
            input_tokens=100,
            output_tokens=42,
            cache_read_input_tokens=80,
            cache_creation_input_tokens=0,
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
        # System prompt has two blocks: cacheable base + language addendum.
        call = fake.calls[0]
        assert len(call["system"]) == 2
        assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
        # User message present.
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


def test_chat_includes_history_in_claude_call() -> None:
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
