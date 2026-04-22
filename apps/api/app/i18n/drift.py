"""Language drift detection (P1.12).

Goal: when the user picked a non-English Nigerian language but Mai Filer's
reply leans heavily toward English anyway, we append a short acknowledgement
in the chosen language so the user isn't silently served English.

We intentionally keep the check lightweight and heuristic — this is a *nudge*,
not a classifier. A full language detection (fastText / langdetect) is a
later optimization; for now the signal is:

  - Split the reply into alphabetic tokens.
  - Count tokens that look like common English function words
    ("the", "is", "your", "and", "for", etc.).
  - If the ratio of English-marker tokens to total alphabetic tokens is above
    the threshold AND the target language is not English, we consider the
    reply to have drifted.

False positives on short "Yes.", "OK.", Naira-number replies are avoided by
skipping when the reply has fewer than 6 alphabetic tokens.
"""

from __future__ import annotations

import re

from app.i18n import LANGUAGES, LanguageCode, get_language

_TOKEN_RE = re.compile(r"[A-Za-z]+")

# Deliberately small, high-precision set of English function words. We avoid
# words that are also common in Pidgin (e.g., "I", "you", "me", "we").
_ENGLISH_MARKERS: frozenset[str] = frozenset(
    {
        "the", "is", "are", "was", "were", "be", "been", "being",
        "and", "but", "or", "nor", "so", "yet",
        "of", "for", "with", "without", "to", "from", "at", "in", "on",
        "this", "that", "these", "those",
        "which", "what", "when", "where", "who", "whom", "whose", "why", "how",
        "your", "their", "our", "its", "his", "hers",
        "have", "has", "had", "having",
        "do", "does", "did", "doing",
        "will", "would", "could", "should", "may", "might",
        "because", "however", "therefore",
    }
)

DRIFT_RATIO_THRESHOLD = 0.22
MIN_TOKENS_TO_EVALUATE = 6

_DRIFT_NOTES: dict[LanguageCode, str] = {
    "ha": (
        "\n\n(Bayanan wannan amsar a cikin Turanci. Idan kana son in yi bayani "
        "fiye a Hausa, ka gaya mini.)"
    ),
    "yo": (
        "\n\n(A se alaye yi ni Geesi. Ti o ba fe ki n salaye daradara ni Yoruba, so fun mi.)"
    ),
    "ig": (
        "\n\n(Azịza a dị n'asụsụ Bekee. Ọ bụrụ na ịchọrọ ka m kọwaa n'Igbo, gwa m.)"
    ),
    "pcm": (
        "\n\n(This reply dey for English. If you want make I explain am for "
        "Pidgin, just tell me.)"
    ),
}


def english_marker_ratio(text: str) -> tuple[float, int]:
    """Return (english_marker_ratio, total_alpha_tokens)."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not tokens:
        return 0.0, 0
    english_hits = sum(1 for t in tokens if t in _ENGLISH_MARKERS)
    return english_hits / len(tokens), len(tokens)


def has_drifted(text: str, target_language: str) -> bool:
    lang = get_language(target_language)
    # English never drifts into English; Pidgin's vocabulary overlaps with
    # English too heavily for this heuristic to be useful — we trust the
    # system prompt for Pidgin.
    if lang.code in {"en", "pcm"}:
        return False
    ratio, total = english_marker_ratio(text)
    if total < MIN_TOKENS_TO_EVALUATE:
        return False
    return ratio >= DRIFT_RATIO_THRESHOLD


def apply_drift_note(text: str, target_language: str) -> str:
    """Return `text` with a localized note appended iff drift is detected."""
    lang = get_language(target_language)
    if not has_drifted(text, lang.code):
        return text
    note = _DRIFT_NOTES.get(lang.code)
    if not note:
        return text
    return text + note


__all__ = [
    "DRIFT_RATIO_THRESHOLD",
    "MIN_TOKENS_TO_EVALUATE",
    "apply_drift_note",
    "english_marker_ratio",
    "has_drifted",
    "LANGUAGES",
]
