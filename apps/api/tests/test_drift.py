"""Language drift fallback tests (P1.13)."""

from __future__ import annotations

from app.i18n.drift import (
    DRIFT_RATIO_THRESHOLD,
    MIN_TOKENS_TO_EVALUATE,
    apply_drift_note,
    english_marker_ratio,
    has_drifted,
)


def test_english_is_never_flagged() -> None:
    text = "The total tax is ₦450,000 for your income this year."
    assert has_drifted(text, "en") is False


def test_heavily_english_output_for_hausa_target_is_flagged() -> None:
    text = (
        "The total tax that you are expected to pay is ₦450,000 for the year, "
        "which is based on the bands that apply to your income."
    )
    ratio, tokens = english_marker_ratio(text)
    assert tokens >= MIN_TOKENS_TO_EVALUATE
    assert ratio >= DRIFT_RATIO_THRESHOLD
    assert has_drifted(text, "ha") is True


def test_apply_drift_note_appends_hausa_marker() -> None:
    text = (
        "The total tax that you are expected to pay is ₦450,000 for the year, "
        "which is based on the bands that apply to your income."
    )
    noted = apply_drift_note(text, "ha")
    assert noted.startswith(text)
    assert "Hausa" in noted or "Turanci" in noted


def test_short_reply_is_never_flagged() -> None:
    assert has_drifted("Yes.", "yo") is False
    assert has_drifted("OK ₦450,000.", "ig") is False


def test_native_language_reply_is_not_flagged() -> None:
    hausa_reply = "Sannu, harajinka na shekara shine ₦450,000."
    yoruba_reply = "E nle, owo ori yin fun odun ni ₦450,000."
    igbo_reply = "Ndewo, ụtụ isi gị maka afọ bụ ₦450,000."
    pcm_reply = "How far! Your tax wey you go pay na ₦450,000."
    assert has_drifted(hausa_reply, "ha") is False
    assert has_drifted(yoruba_reply, "yo") is False
    assert has_drifted(igbo_reply, "ig") is False
    # Pidgin uses English vocabulary, so we expect it to NOT trigger often.
    assert has_drifted(pcm_reply, "pcm") is False


def test_apply_drift_note_is_noop_when_text_is_native() -> None:
    yoruba_reply = "E nle, owo ori yin fun odun ni ₦450,000."
    assert apply_drift_note(yoruba_reply, "yo") == yoruba_reply
