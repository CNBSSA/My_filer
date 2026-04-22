"""Mai Filer internationalization registry.

Per ADR-0004, v1 ships five languages. Each entry provides:
- `display_name`: the language in its own script (for the UI selector).
- `system_addendum`: a block appended to the Claude system prompt that steers
  Mai Filer to speak in that language with culturally appropriate tone.
- `greeting`: fallback greeting used in tests and smoke flows.

NRS filing payloads are always English by regulation (ADR-0004 consequences).
UI strings live in `apps/web/messages/{code}.json` (separate concern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LanguageCode = Literal["en", "ha", "yo", "ig", "pcm"]


@dataclass(frozen=True)
class Language:
    code: LanguageCode
    display_name: str
    english_name: str
    system_addendum: str
    greeting: str


_EN = Language(
    code="en",
    display_name="English",
    english_name="English",
    system_addendum=(
        "Respond in clear, professional Nigerian English. Use Naira with the "
        "₦ symbol and thousands separators (e.g., ₦1,250,000). When quoting "
        "tax rules, cite them by plain name (e.g., 'NTAA 2026') without "
        "legalese. Prefer short sentences."
    ),
    greeting="Hello, I'm Mai Filer. How can I help with your taxes today?",
)

_HA = Language(
    code="ha",
    display_name="Hausa",
    english_name="Hausa",
    system_addendum=(
        "Amsa da Hausa mai sauki kuma mai ladabi. Yi amfani da Naira tare "
        "da alamar naira da ragi (misali, ₦1,250,000). Idan kana yin bayani "
        "a kan dokar haraji, yi shi cikin harshen da taxpayer zai iya "
        "fahimta. Yi amfani da jimloli gajeru. Kada ka bar kalmomin fasaha "
        "ba bayanin Hausa ba."
    ),
    greeting="Sannu, ni Mai Filer ce. Yaya zan taimaka maka da harajinka yau?",
)

_YO = Language(
    code="yo",
    display_name="Yoruba",
    english_name="Yoruba",
    system_addendum=(
        "Da si Yoruba to mogbon ati to ni oyaya. Lo Naira pelu ami naira "
        "ati ami ipinya (apere, ₦1,250,000). Nigba ti o ba n salaye ilana "
        "owo ori, salaye ni ede ti won le loye. Fi awon gbolohun kukuru lo. "
        "Maa salaye awon oro imo-ero ti o ba lo."
    ),
    greeting="E nle, oruko mi ni Mai Filer. Bawo ni mo se le ran yin lowo lori owo ori yin loni?",
)

_IG = Language(
    code="ig",
    display_name="Igbo",
    english_name="Igbo",
    system_addendum=(
        "Zaghachi n'Igbo di mfe ma kwanyere ugwu. Jiri Naira yana akara "
        "naira yana akara nkewa (dika, ₦1,250,000). Mgbe i na-akowa iwu utu "
        "isi, mee ya n'asusu onye na-atu utu isi ga-aghota. Jiri ahiriokwu "
        "di mkpirikpi. Ighaghi ikowa okwu ogbara ohuru i na-eji."
    ),
    greeting="Ndewo, aha m bu Mai Filer. Kedu ka m ga-esi nyere gi aka n'utu isi gi taa?",
)

_PCM = Language(
    code="pcm",
    display_name="Naija (Pidgin)",
    english_name="Nigerian Pidgin",
    system_addendum=(
        "Answer for clear Nigerian Pidgin. Use Naira with ₦ sign and comma "
        "separator (like ₦1,250,000). When you dey explain tax rule, make "
        "you talk am simple — no big grammar. Short sentence dey better. "
        "If you use any technical word, explain am sharp-sharp."
    ),
    greeting="How far, I be Mai Filer. How I fit help you with your tax today?",
)

LANGUAGES: dict[LanguageCode, Language] = {
    "en": _EN,
    "ha": _HA,
    "yo": _YO,
    "ig": _IG,
    "pcm": _PCM,
}

DEFAULT_LANGUAGE: LanguageCode = "en"


def get_language(code: str | None) -> Language:
    """Return the language config for a given code; default English on miss."""
    if not code:
        return LANGUAGES[DEFAULT_LANGUAGE]
    normalized = code.lower().strip()
    if normalized in LANGUAGES:
        return LANGUAGES[normalized]  # type: ignore[index]
    return LANGUAGES[DEFAULT_LANGUAGE]


def list_supported() -> list[dict[str, str]]:
    """UI-friendly list for the language selector."""
    return [
        {"code": lang.code, "label": lang.display_name, "english": lang.english_name}
        for lang in LANGUAGES.values()
    ]
