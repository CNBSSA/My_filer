"""Mai Filer API entrypoint.

Mounts every phase router plus the observability surface:

  * CORS middleware (env-driven allow-list).
  * CorrelationIdMiddleware — reads / mints `X-Request-Id`, binds it to
    logs via a contextvars context.
  * /health — liveness probe.
  * /metrics — Prometheus text-exposition format.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.filings import router as filings_router
from app.api.identity import router as identity_router
from app.api.memory import router as memory_router
from app.api.ngo_filings import router as ngo_router
from app.config import get_settings
from app.observability import (
    CorrelationIdMiddleware,
    configure_json_logging,
    metrics_router,
)

settings = get_settings()

# Configure structured logging before anything else prints.
configure_json_logging(level=settings.log_level)

app = FastAPI(
    title="Mai Filer API",
    description=(
        "AI-native Nigerian tax e-filing platform. "
        "Mai Filer orchestrates tax calculation, document intelligence, "
        "compliance, and NRS filing."
    ),
    version=__version__,
)

# Middleware order: outermost is CORS (pre-flight short-circuit), then
# correlation ID so every request — including the pre-flighted one — has
# an ID bound when any downstream log fires.
app.add_middleware(
    CorrelationIdMiddleware, header=settings.correlation_id_header
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
app.include_router(identity_router)
app.include_router(memory_router)
app.include_router(ngo_router)
app.include_router(metrics_router)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe. Never depends on downstream services."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "version": __version__,
    }
