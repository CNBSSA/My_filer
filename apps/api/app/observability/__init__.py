"""Observability (P7.5).

Three pieces:

  * `json_logging`  — configure stdlib `logging` to emit one-line JSON
                      records per event.
  * `CorrelationIdMiddleware` — reads / generates an `X-Request-Id` on
                      every HTTP request and threads it through logs
                      via a `contextvars` binding.
  * `metrics`       — process-local counters + latency histograms, and
                      a `/metrics` endpoint that renders them in the
                      Prometheus text-exposition format. No external
                      dep required; pure stdlib.
"""

from __future__ import annotations

from app.observability.correlation import (
    CorrelationIdMiddleware,
    current_correlation_id,
    set_correlation_id,
)
from app.observability.json_logging import configure_json_logging
from app.observability.metrics import (
    counter,
    histogram,
    metrics_router,
    observe,
)

__all__ = [
    "CorrelationIdMiddleware",
    "configure_json_logging",
    "counter",
    "current_correlation_id",
    "histogram",
    "metrics_router",
    "observe",
    "set_correlation_id",
]
