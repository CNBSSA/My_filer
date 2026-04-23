"""Observability tests (P7.5): JSON logging, correlation IDs, /metrics."""

from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import json_logging
from app.observability.correlation import current_correlation_id, set_correlation_id
from app.observability.metrics import counter, observe, render_text, reset


# ---------------------------------------------------------------------------
# JSON logging
# ---------------------------------------------------------------------------


def test_json_formatter_emits_one_line_json(capsys) -> None:
    json_logging.configure_json_logging(level="DEBUG")
    logger = logging.getLogger("mai_filer.tests.json_log")
    logger.info("hello world", extra={"user": "chidi", "amount": 5_000_000})

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "no log line captured"
    record = json.loads(captured[-1])
    assert record["level"] == "INFO"
    assert record["message"] == "hello world"
    assert record["user"] == "chidi"
    assert record["amount"] == 5_000_000
    assert "ts" in record


def test_json_formatter_carries_correlation_id(capsys) -> None:
    json_logging.configure_json_logging(level="INFO")
    logger = logging.getLogger("mai_filer.tests.correlation")
    set_correlation_id("req-123")
    try:
        logger.info("with correlation")
        captured = capsys.readouterr().out.strip().splitlines()
        record = json.loads(captured[-1])
        assert record["correlation_id"] == "req-123"
    finally:
        set_correlation_id(None)


# ---------------------------------------------------------------------------
# CorrelationIdMiddleware
# ---------------------------------------------------------------------------


def test_correlation_middleware_mints_id_when_absent() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    header = response.headers.get("X-Request-Id")
    assert header and len(header) >= 16


def test_correlation_middleware_echoes_inbound_id() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-Id": "caller-supplied-42"})
    assert response.headers["X-Request-Id"] == "caller-supplied-42"


def test_correlation_middleware_unbinds_after_request() -> None:
    client = TestClient(app)
    client.get("/health", headers={"X-Request-Id": "aaa"})
    # Once the request has returned, the ContextVar should be cleared
    # in the main task — the default is None outside request scope.
    assert current_correlation_id() is None


# ---------------------------------------------------------------------------
# /metrics endpoint + render
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset()
    yield
    reset()


def test_counter_increments_and_renders() -> None:
    counter("filings_submitted_total", outcome="simulated")
    counter("filings_submitted_total", outcome="simulated", by=2)
    counter("filings_submitted_total", outcome="rejected")
    body = render_text()
    assert 'filings_submitted_total{outcome="simulated"} 3.0' in body
    assert 'filings_submitted_total{outcome="rejected"} 1.0' in body
    assert "# TYPE filings_submitted_total counter" in body


def test_histogram_records_latency_buckets() -> None:
    observe("gateway_latency_seconds", 0.12, scheme="hmac")
    observe("gateway_latency_seconds", 0.75, scheme="hmac")
    observe("gateway_latency_seconds", 3.0, scheme="hmac")
    body = render_text()
    assert 'gateway_latency_seconds_bucket{scheme="hmac",le="0.25"}' in body
    assert 'gateway_latency_seconds_bucket{scheme="hmac",le="+Inf"} 3' in body
    assert 'gateway_latency_seconds_sum{scheme="hmac"} 3.87' in body
    assert 'gateway_latency_seconds_count{scheme="hmac"} 3' in body


def test_metrics_endpoint_serves_text_exposition() -> None:
    counter("mai_requests_total", path="/health")
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'mai_requests_total{path="/health"} 1.0' in response.text
