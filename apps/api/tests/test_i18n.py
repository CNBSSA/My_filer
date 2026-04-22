"""i18n registry tests (ADR-0004)."""

from app.i18n import DEFAULT_LANGUAGE, LANGUAGES, get_language, list_supported


def test_v1_ships_five_languages() -> None:
    assert set(LANGUAGES.keys()) == {"en", "ha", "yo", "ig", "pcm"}


def test_default_is_english() -> None:
    assert DEFAULT_LANGUAGE == "en"
    assert get_language(None).code == "en"
    assert get_language("").code == "en"
    assert get_language("unknown").code == "en"


def test_each_language_has_addendum_and_greeting() -> None:
    for lang in LANGUAGES.values():
        assert lang.system_addendum.strip(), f"{lang.code} missing addendum"
        assert lang.greeting.strip(), f"{lang.code} missing greeting"


def test_get_language_case_insensitive() -> None:
    assert get_language("HA").code == "ha"
    assert get_language(" yo ").code == "yo"


def test_list_supported_shape() -> None:
    items = list_supported()
    assert len(items) == 5
    for item in items:
        assert {"code", "label", "english"} == set(item.keys())
