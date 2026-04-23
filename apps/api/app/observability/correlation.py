"""Correlation-ID context + FastAPI middleware."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_correlation_id: ContextVar[str | None] = ContextVar("mai_filer_correlation_id", default=None)

DEFAULT_HEADER = "X-Request-Id"


def current_correlation_id() -> str | None:
    """The correlation ID bound to the current task, if any."""
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> None:
    """Tests / workers override the binding explicitly."""
    _correlation_id.set(value)


def _new_correlation_id() -> str:
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Pull `X-Request-Id` from inbound requests, mint one when absent, thread
    it through logs + response headers.
    """

    def __init__(self, app: ASGIApp, *, header: str = DEFAULT_HEADER) -> None:
        super().__init__(app)
        self._header = header

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        incoming = request.headers.get(self._header)
        correlation_id = incoming or _new_correlation_id()
        token = _correlation_id.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers[self._header] = correlation_id
        return response
