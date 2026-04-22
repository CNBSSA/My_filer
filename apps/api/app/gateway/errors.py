"""NRS error-code translator (P6.8).

NRS returns a `code` + `message` per rejection. Mai Filer's job is to turn
that into a plain-language explanation in the taxpayer's chosen language
so they know what to fix.

The catalogue below is v1 — it covers the rejection classes we can
confidently anticipate (auth, payload shape, identity, math). When NRS
publishes a definitive error list we extend this map rather than the
parsing logic. Codes are string to match the NRS convention.

Per ADR-0004, localized explanations cover en / ha / yo / ig / pcm. If a
locale entry is missing we fall back to English.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["retryable", "user_fix", "fatal"]


@dataclass(frozen=True)
class NRSError:
    code: str
    severity: Severity
    # Per-language plain-language message. "en" is always present.
    messages: dict[str, str]


# Intentionally small, high-signal set. Unknown codes fall through to
# NRS_UNKNOWN with the vendor's raw message attached.
_CATALOGUE: dict[str, NRSError] = {
    "NRS-AUTH-001": NRSError(
        code="NRS-AUTH-001",
        severity="fatal",
        messages={
            "en": (
                "Your NRS client credentials were rejected. Ask the owner / admin "
                "to refresh the NRS API key and business ID, then retry."
            ),
            "ha": (
                "NRS ta ki shaidar abokin cinikinku. Nemi mai gudanarwa ya sabunta "
                "maɓallin NRS da ID na kasuwanci, sannan a sake gwada."
            ),
            "yo": (
                "NRS ko gba awọn iwe-ẹri rẹ. Beere lọwọ adari lati tun NRS API key "
                "ati business ID ṣe, lẹhinna gbiyanju lẹẹkan sii."
            ),
            "ig": (
                "NRS ekweghị nkwenye gị. Rịọ onye njikwa ka ọ gbanwee NRS API key "
                "na business ID, mesịa nwaa ọzọ."
            ),
            "pcm": (
                "NRS no gree your login. Tell admin make im refresh the NRS API "
                "key and business ID, then try again."
            ),
        },
    ),
    "NRS-SIGNATURE-001": NRSError(
        code="NRS-SIGNATURE-001",
        severity="retryable",
        messages={
            "en": (
                "NRS rejected the request signature. The clock may have drifted "
                "or the secret was rotated. The system will retry; if this "
                "persists, an operator must re-key."
            ),
            "pcm": (
                "NRS say the request signature no correct. E fit be clock drift "
                "or rotated secret. System go retry am."
            ),
        },
    ),
    "NRS-REPLAY-001": NRSError(
        code="NRS-REPLAY-001",
        severity="retryable",
        messages={
            "en": (
                "NRS rejected the request because the timestamp was outside the "
                "replay window. The system will retry with a fresh timestamp."
            ),
        },
    ),
    "NRS-NIN-NOT-FOUND": NRSError(
        code="NRS-NIN-NOT-FOUND",
        severity="user_fix",
        messages={
            "en": (
                "NRS does not recognize this NIN yet. New NINs can take 24–72 "
                "hours to propagate from NIMC. Try again later, or verify the "
                "NIN digits with the taxpayer."
            ),
            "pcm": (
                "NRS never see this NIN. New NIN fit take 24–72 hours to show. "
                "Try later, or check the NIN well-well."
            ),
        },
    ),
    "NRS-PAYLOAD-001": NRSError(
        code="NRS-PAYLOAD-001",
        severity="user_fix",
        messages={
            "en": (
                "The filing payload failed NRS schema validation. Run Audit "
                "Shield again — it will pinpoint the missing or malformed "
                "field before resubmitting."
            ),
        },
    ),
    "NRS-COMPUTATION-001": NRSError(
        code="NRS-COMPUTATION-001",
        severity="user_fix",
        messages={
            "en": (
                "NRS recomputed the total tax and disagreed with the declared "
                "figure. Re-run `calc_paye` with the current deductions, "
                "update the return, and resubmit."
            ),
        },
    ),
    "NRS-RATE-LIMIT": NRSError(
        code="NRS-RATE-LIMIT",
        severity="retryable",
        messages={
            "en": (
                "NRS asked us to slow down. The system will retry after a "
                "backoff; no action required from you."
            ),
        },
    ),
    "NRS-UPSTREAM-DOWN": NRSError(
        code="NRS-UPSTREAM-DOWN",
        severity="retryable",
        messages={
            "en": (
                "NRS servers are temporarily unavailable. The system will "
                "retry; if the outage persists we will notify the operator."
            ),
            "pcm": (
                "NRS server dey down small. System go try again; if e still "
                "no work, we go tell admin."
            ),
        },
    ),
}


UNKNOWN = NRSError(
    code="NRS-UNKNOWN",
    severity="retryable",
    messages={
        "en": (
            "NRS returned an unexpected error. We will retry once; if it "
            "persists, the raw vendor message is attached for the operator."
        ),
    },
)


def translate_error(*, code: str, language: str = "en") -> dict[str, str]:
    """Return a dict ready to surface to the user:

        {"code": ..., "severity": ..., "message": <localized plain-language>}
    """
    entry = _CATALOGUE.get(code) or UNKNOWN
    message = entry.messages.get(language) or entry.messages["en"]
    return {
        "code": entry.code if entry is not UNKNOWN else code,
        "severity": entry.severity,
        "message": message,
    }


def known_codes() -> list[str]:
    return sorted(_CATALOGUE.keys())
