"""Celery async-pipeline tests (P6.4 / P6.5).

The production wiring is `CELERY_ENABLED=true` + a worker process. Tests
flip `task_always_eager=True` so `.delay(...)` runs the task inline in
the current process — which gives us end-to-end coverage of the task
registration, argument plumbing, and result-dict shape without needing
a real broker.

`is_async_enabled()` intentionally returns False in eager mode so the
inline path of the endpoint stays covered too; we poke the helper
directly to prove that logic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.filings import get_storage as filings_get_storage
from app.celery_app import celery_app, is_async_enabled
from app.documents.storage import InMemoryStorage
from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


def _payload() -> dict[str, Any]:
    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
            residential_address="1 Ikoyi Crescent, Lagos",
        ),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
        ],
        declaration=True,
    ).model_dump(mode="json")


def _override_storage() -> InMemoryStorage:
    storage = InMemoryStorage()
    app.dependency_overrides[filings_get_storage] = lambda: storage
    return storage


def _finalized_filing_id(client: TestClient) -> str:
    filing_id = client.post("/v1/filings", json=_payload()).json()["id"]
    client.post(f"/v1/filings/{filing_id}/audit")
    client.post(f"/v1/filings/{filing_id}/pack")
    return filing_id


def test_is_async_enabled_requires_both_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eager + enabled = still inline; only true toggle makes dispatch go async."""
    from app.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.celery_enabled is False
    assert is_async_enabled() is False

    monkeypatch.setattr(s, "celery_enabled", True)
    monkeypatch.setattr(s, "celery_task_eager", True)
    assert is_async_enabled() is False  # eager mode stays inline-compatible

    monkeypatch.setattr(s, "celery_task_eager", False)
    assert is_async_enabled() is True
    get_settings.cache_clear()


def test_submit_task_eager_matches_sync_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running the Celery task in eager mode must produce the same outcome dict
    as calling `submit_filing_to_nrs` inline — no NRS creds → simulated."""
    from app.tasks.filing_tasks import submit_filing_to_nrs_task

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    _override_storage()
    try:
        client = TestClient(app)
        filing_id = _finalized_filing_id(client)

        result = submit_filing_to_nrs_task.delay(filing_id=filing_id, language="en")
        payload = result.get(timeout=5)

        assert payload["filing_id"] == filing_id
        assert payload["status"] == "simulated"
        assert payload["simulated"] is True
        assert payload["irn"].startswith("SIM-IRN-")
        assert payload["csid"].startswith("SIM-CSID-")
    finally:
        app.dependency_overrides.clear()


def test_submit_endpoint_inline_when_async_flag_off() -> None:
    """Default path: `async_=false` → synchronous submission + {submission: ...}."""
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = _finalized_filing_id(client)

        resp = client.post(
            f"/v1/filings/{filing_id}/submit",
            json={"language": "en", "async_": False},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "submission" in body
        assert "queued" not in body
        assert body["submission"]["status"] == "simulated"
    finally:
        app.dependency_overrides.clear()


def test_submit_endpoint_enqueues_when_async_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `CELERY_ENABLED=true` and eager=False, endpoint should enqueue
    and return {queued: true, task_id}. We stub `.delay` so we don't need
    a real broker running in the test environment."""
    from app.config import get_settings
    from app.tasks import filing_tasks

    get_settings.cache_clear()
    s = get_settings()
    monkeypatch.setattr(s, "celery_enabled", True)
    monkeypatch.setattr(s, "celery_task_eager", False)

    captured: dict[str, Any] = {}

    class _FakeAsyncResult:
        id = "fake-task-id-42"

    def _fake_delay(*, filing_id: str, language: str = "en") -> _FakeAsyncResult:
        captured["filing_id"] = filing_id
        captured["language"] = language
        return _FakeAsyncResult()

    monkeypatch.setattr(
        filing_tasks.submit_filing_to_nrs_task, "delay", _fake_delay
    )

    _override_storage()
    try:
        client = TestClient(app)
        filing_id = _finalized_filing_id(client)

        resp = client.post(
            f"/v1/filings/{filing_id}/submit",
            json={"language": "en", "async_": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["queued"] is True
        assert body["task_id"] == "fake-task-id-42"
        assert "submission" not in body
        assert captured == {"filing_id": filing_id, "language": "en"}
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_submit_endpoint_async_flag_honours_disabled_flag() -> None:
    """Client asks for async, but `CELERY_ENABLED=false` → silently falls
    back to inline. This is the dev-default behaviour and must not error."""
    _override_storage()
    try:
        client = TestClient(app)
        filing_id = _finalized_filing_id(client)

        resp = client.post(
            f"/v1/filings/{filing_id}/submit",
            json={"language": "en", "async_": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # CELERY_ENABLED defaults to False → we take the inline path.
        assert "submission" in body
        assert "queued" not in body
        assert body["submission"]["status"] == "simulated"
    finally:
        app.dependency_overrides.clear()


def test_submit_task_returns_error_when_filing_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: a stale task targeting a deleted filing should degrade
    gracefully rather than raise and trigger retries forever."""
    from app.tasks.filing_tasks import submit_filing_to_nrs_task

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    result = submit_filing_to_nrs_task.delay(
        filing_id="nonexistent-filing-id", language="en"
    )
    payload = result.get(timeout=5)
    assert payload["error"] == "filing not found"
    assert payload["filing_id"] == "nonexistent-filing-id"
