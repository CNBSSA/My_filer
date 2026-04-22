"""Mai Filer API entrypoint.

The FastAPI app exposes a minimal /health endpoint at Phase 0. Future phases
wire the chat, documents, filing, identity, and gateway routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.filings import router as filings_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Mai Filer API",
    description=(
        "AI-native Nigerian tax e-filing platform. "
        "Mai Filer orchestrates tax calculation, document intelligence, "
        "compliance, and NRS filing."
    ),
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(filings_router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe. Never depends on downstream services."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "version": __version__,
    }
