"""Mai Filer API entrypoint.

Mounts every phase router plus the observability surface:

  * CORS middleware (env-driven allow-list).
  * CorrelationIdMiddleware — reads / mints `X-Request-Id`, binds it to
    logs via a contextvars context.
  * /health — liveness probe (public).
  * /metrics — Prometheus text-exposition format (protected by API_TOKEN).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.limits import limiter

from app import __version__
from app.api.auth import require_api_token
from app.api.chat import router as chat_router
from app.api.corporate_filings import router as corporate_filings_router
from app.api.documents import router as documents_router
from app.api.filings import router as filings_router
from app.api.identity import router as identity_router
from app.api.memory import router as memory_router
from app.api.ngo_filings import router as ngo_router
from app.api.sme import router as sme_router
from app.config import get_settings
from app.observability import (
    CorrelationIdMiddleware,
    configure_json_logging,
    metrics_router,
)

settings = get_settings()

# Configure structured logging before anything else prints.
configure_json_logging(level=settings.log_level)


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """Fail fast on misconfigured environments before serving any traffic."""
    settings.validate_for_env()
    yield


app = FastAPI(
    title="Mai Filer API",
    lifespan=_lifespan,
    description=(
        "AI-native Nigerian tax e-filing platform. "
        "Mai Filer orchestrates tax calculation, document intelligence, "
        "compliance, and NRS filing."
    ),
    version=__version__,
)

# Rate limiting — must be registered before middleware is added.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware order: outermost is CORS (pre-flight short-circuit), then
# SlowAPI for rate limiting, then correlation ID so every request has an
# ID bound when any downstream log fires.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CorrelationIdMiddleware, header=settings.correlation_id_header
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id", "Accept"],
)

# Auth-protected routers.  documents_router and memory_router carry their own
# router-level dependency; the remaining routers get auth applied here so
# every PII-touching route is guarded without touching each file.
_auth = [Depends(require_api_token)]

app.include_router(chat_router, dependencies=_auth)
app.include_router(corporate_filings_router, dependencies=_auth)
app.include_router(documents_router)        # own router-level dependency
app.include_router(filings_router, dependencies=_auth)
app.include_router(identity_router, dependencies=_auth)
app.include_router(memory_router)           # own router-level dependency
app.include_router(ngo_router, dependencies=_auth)
app.include_router(sme_router, dependencies=_auth)
app.include_router(metrics_router, dependencies=_auth)   # protect /metrics


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe. Never depends on downstream services. Public endpoint."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "version": __version__,
    }
