"""Name-match tests (P5.8)."""

from __future__ import annotations

from app.identity.name_match import fuzzy_match, strict_match


def test_strict_match_exact_after_casefold() -> None:
    assert strict_match("Chidi Okafor", "CHIDI OKAFOR")
    assert strict_match("  Chidi  Okafor  ", "chidi okafor")


def test_strict_match_differs_with_middle_name() -> None:
    assert not strict_match("Chidi Okafor", "Chidi Emeka Okafor")


def test_fuzzy_match_tolerates_middle_name() -> None:
    result = fuzzy_match("Chidi Okafor", "Chidi Emeka Okafor")
    assert result.ok is True
    # Record has one extra token ("emeka") that's missing from the declared
    # name, but the remaining token overlap still passes.
    assert "emeka" in result.missing_tokens


def test_fuzzy_match_tolerates_accents() -> None:
    result = fuzzy_match("Oluwafunke Adelabu", "Olúwafúnké Adelabu")
    assert result.ok is True


def test_fuzzy_match_rejects_mismatched_names() -> None:
    result = fuzzy_match("Chidi Okafor", "Grace Ibrahim")
    assert result.ok is False


def test_fuzzy_match_tolerates_typos() -> None:
    result = fuzzy_match("Chidi Okafor", "Chidi Okafor ")  # trailing space
    assert result.ok
    result = fuzzy_match("Chidi Okafor", "Chidi Okafot")  # 1-char typo in surname
    # 11/12 chars → similarity > 0.85 threshold.
    assert result.ok


def test_fuzzy_match_empty_inputs_are_not_ok() -> None:
    assert fuzzy_match("", "Chidi Okafor").ok is False
    assert fuzzy_match("Chidi Okafor", "").ok is False
