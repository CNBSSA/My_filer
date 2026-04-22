"""Chat router — Phase 1 non-streaming endpoint (P1.5) + language list (P1.11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.mai_filer.orchestrator import (
    MaiFilerOrchestrator,
    build_default_orchestrator,
)
from app.agents.mai_filer.schemas import ChatRequest, ChatResponse, LanguageInfo
from app.config import get_settings
from app.i18n import list_supported

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
) -> ChatResponse:
    """Single-turn Mai Filer chat (Phase 1).

    Streaming (SSE) arrives in P1.7; DB-backed thread persistence in P1.8/P1.9.
    """
    settings = get_settings()
    if not settings.anthropic_api_key and orchestrator is build_default_orchestrator():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANTHROPIC_API_KEY not configured",
        )
    return orchestrator.chat(request)
