"""Dojah adapter tests (P5.2) — mocked HttpClient, no network."""

from __future__ import annotations

import pytest

from app.identity.base import AggregatorError
from app.identity.dojah import DojahAdapter


class FakeResponse:
    def __init__(self, *, status_code: int, body: dict | str | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = body if isinstance(body, str) else ""

    def json(self):  # noqa: D401
        return self._body if isinstance(self._body, dict) else {}


class FakeHttp:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self._response = response
        self.calls: list[dict] = []

    def get(self, url, *, headers, params, timeout):
        self.calls.append(
            {"url": url, "headers": headers, "params": params, "timeout": timeout}
        )
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


NIN = "12345678901"


def _adapter(response: FakeResponse | Exception) -> tuple[DojahAdapter, FakeHttp]:
    http = FakeHttp(response)
    return (
        DojahAdapter(api_key="test-key", app_id="test-app", http=http),
        http,
    )


def test_dojah_happy_path_maps_entity_to_verification() -> None:
    adapter, http = _adapter(
        FakeResponse(
            status_code=200,
            body={
                "entity": {
                    "nin": NIN,
                    "first_name": "Chidi",
                    "middle_name": "Emeka",
                    "last_name": "Okafor",
                    "date_of_birth": "1990-04-12",
                    "gender": "M",
                    "state_of_origin": "Anambra",
                    "phone_number": "+2348012345678",
                }
            },
        )
    )
    result = adapter.verify_nin(NIN, consent=True)
    assert result.valid is True
    assert result.aggregator == "dojah"
    assert result.first_name == "Chidi"
    assert result.last_name == "Okafor"
    assert result.middle_name == "Emeka"
    assert result.canonical_full_name() == "Chidi Emeka Okafor"
    assert result.phone == "+2348012345678"
    assert result.raw["entity"]["nin"] == NIN
    # Auth headers present.
    call = http.calls[0]
    assert call["headers"]["AppId"] == "test-app"
    assert call["headers"]["Authorization"] == "test-key"
    assert call["params"] == {"nin": NIN}


def test_dojah_requires_consent() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=200, body={"entity": {}}))
    with pytest.raises(PermissionError):
        adapter.verify_nin(NIN, consent=False)


def test_dojah_validates_nin_format() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=200, body={}))
    with pytest.raises(ValueError):
        adapter.verify_nin("abc", consent=True)
    with pytest.raises(ValueError):
        adapter.verify_nin("12345", consent=True)


def test_dojah_4xx_returns_invalid_not_raises() -> None:
    adapter, _ = _adapter(
        FakeResponse(status_code=404, body={"error": "NIN not found"})
    )
    result = adapter.verify_nin(NIN, consent=True)
    assert result.valid is False
    assert result.error is not None
    assert "NIN not found" in result.error


def test_dojah_5xx_escalates_as_aggregator_error() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=503, body="upstream down"))
    with pytest.raises(AggregatorError):
        adapter.verify_nin(NIN, consent=True)


def test_dojah_transport_exception_escalates() -> None:
    adapter, _ = _adapter(RuntimeError("connection refused"))
    with pytest.raises(AggregatorError):
        adapter.verify_nin(NIN, consent=True)


def test_dojah_empty_entity_marks_invalid() -> None:
    adapter, _ = _adapter(FakeResponse(status_code=200, body={"entity": {}}))
    result = adapter.verify_nin(NIN, consent=True)
    assert result.valid is False
    assert result.error == "incomplete identity record"
