"""NRS error translator tests (P6.8)."""

from __future__ import annotations

from app.gateway.errors import known_codes, translate_error


def test_known_codes_listed() -> None:
    codes = known_codes()
    for c in [
        "NRS-AUTH-001",
        "NRS-SIGNATURE-001",
        "NRS-REPLAY-001",
        "NRS-NIN-NOT-FOUND",
        "NRS-PAYLOAD-001",
        "NRS-COMPUTATION-001",
        "NRS-RATE-LIMIT",
        "NRS-UPSTREAM-DOWN",
    ]:
        assert c in codes


def test_translate_returns_english_by_default() -> None:
    t = translate_error(code="NRS-AUTH-001")
    assert t["code"] == "NRS-AUTH-001"
    assert t["severity"] == "fatal"
    assert "client credentials" in t["message"].lower()


def test_translate_uses_localized_message_when_available() -> None:
    t_en = translate_error(code="NRS-AUTH-001", language="en")
    t_ha = translate_error(code="NRS-AUTH-001", language="ha")
    assert t_en["message"] != t_ha["message"]


def test_translate_falls_back_to_english_for_missing_locale() -> None:
    t_yo = translate_error(code="NRS-PAYLOAD-001", language="yo")
    # We didn't ship a yo message for this code — fall back to en.
    assert "schema validation" in t_yo["message"].lower()


def test_translate_unknown_code_preserves_vendor_code() -> None:
    t = translate_error(code="WHATEVER-42")
    assert t["code"] == "WHATEVER-42"
    assert t["severity"] in {"retryable", "user_fix", "fatal"}


def test_severity_matrix_for_known_codes() -> None:
    assert translate_error(code="NRS-NIN-NOT-FOUND")["severity"] == "user_fix"
    assert translate_error(code="NRS-RATE-LIMIT")["severity"] == "retryable"
    assert translate_error(code="NRS-AUTH-001")["severity"] == "fatal"
