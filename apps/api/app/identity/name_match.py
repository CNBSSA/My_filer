"""Name matching between the NIN record and the taxpayer's declared name (P5.8).

Two levels:
  - `strict_match`: exact match after normalization (case + whitespace +
    punctuation collapsed). Used when the user explicitly typed their
    name to match the NIN record.
  - `fuzzy_match`: token-based + character similarity tolerant of middle
    names, ordering, and minor typos. Used for the soft check that Mai
    Filer runs automatically before the Audit Shield.

No external deps — stdlib `difflib` is good enough for the NIN record's
short names and keeps the deploy surface minimal.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(value: str) -> str:
    if not value:
        return ""
    lowered = value.lower().strip()
    # Strip accents so "Olúwafúnké" ≈ "Oluwafunke".
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    without_punct = _PUNCT_RE.sub(" ", ascii_only)
    return _WHITESPACE_RE.sub(" ", without_punct).strip()


def _tokens(value: str) -> set[str]:
    return {t for t in _normalize(value).split(" ") if t}


def strict_match(declared: str, nin_record: str) -> bool:
    """Exact match after normalization."""
    return bool(declared) and bool(nin_record) and _normalize(declared) == _normalize(nin_record)


@dataclass(frozen=True)
class FuzzyResult:
    ok: bool
    similarity: float
    declared_normalized: str
    record_normalized: str
    missing_tokens: list[str]

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "similarity": round(self.similarity, 3),
            "declared": self.declared_normalized,
            "record": self.record_normalized,
            "missing_tokens": list(self.missing_tokens),
        }


FUZZY_THRESHOLD = 0.85
TOKEN_MIN_OVERLAP = 0.5  # proportion of record tokens that must appear in declared


def fuzzy_match(
    declared: str,
    nin_record: str,
    *,
    threshold: float = FUZZY_THRESHOLD,
    min_token_overlap: float = TOKEN_MIN_OVERLAP,
) -> FuzzyResult:
    """Lenient match. Passes when:

    1. Character-level similarity (SequenceMatcher ratio) >= `threshold`, OR
    2. At least `min_token_overlap` fraction of the record's tokens appear
       in the declared name (covers 'Chidi Emeka Okafor' vs 'Chidi Okafor').
    """
    declared_norm = _normalize(declared)
    record_norm = _normalize(nin_record)

    if not declared_norm or not record_norm:
        return FuzzyResult(
            ok=False,
            similarity=0.0,
            declared_normalized=declared_norm,
            record_normalized=record_norm,
            missing_tokens=[],
        )

    similarity = SequenceMatcher(None, declared_norm, record_norm).ratio()
    declared_tokens = _tokens(declared)
    record_tokens = _tokens(nin_record)
    missing = sorted(record_tokens - declared_tokens)
    overlap = 0.0
    if record_tokens:
        overlap = 1.0 - (len(missing) / len(record_tokens))

    ok = similarity >= threshold or overlap >= min_token_overlap
    return FuzzyResult(
        ok=ok,
        similarity=similarity,
        declared_normalized=declared_norm,
        record_normalized=record_norm,
        missing_tokens=missing,
    )
