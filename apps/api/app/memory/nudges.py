"""Mid-year nudges (P8.5).

Given a taxpayer's year-to-date gross income and their prior-year
facts, Mai Filer should be able to say things like:

  "At this pace you're annualizing ₦9.2m, up 35% from last year —
   that moves you from band 3 to band 4; consider a ₦300k pension
   top-up to keep the marginal rate at 18%."

This module produces the structured inputs to those explanations. The
actual wording is Mai's job (Role 5). Keeping the math + detection
here makes it testable and language-agnostic.

Nothing here fetches external rates — PIT bands come from
`app.tax.pit.PIT_BANDS_2026` (locked data) and the VAT threshold from
`app.tax.vat`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import YearlyFact
from app.tax.pit import PIT_BANDS_2026, PITBand
from app.tax.vat import REGISTRATION_THRESHOLD

Severity = Literal["info", "watch", "alert"]


@dataclass(frozen=True)
class Nudge:
    code: str
    severity: Severity
    message: str
    meta: dict

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "meta": dict(self.meta),
        }


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def annualize(ytd_amount: Decimal, *, month: int) -> Decimal:
    """Project YTD to a full-year figure using the month index.

    `month` is 1-12; month 6 means "half the year has passed", so the
    annualized figure is `ytd * 12 / 6`. Clamps `month` to [1, 12].
    """
    m = max(1, min(12, month))
    return (ytd_amount * Decimal(12)) / Decimal(m)


def _band_for(income: Decimal, bands: tuple[PITBand, ...] = PIT_BANDS_2026) -> PITBand:
    """Return the PIT band that the last naira of `income` falls into."""
    for band in bands:
        upper = band.upper
        if upper is None or income <= upper:
            return band
    return bands[-1]


def suggest_nudges(
    session: Session,
    *,
    user_nin_hash: str | None,
    current_year: int,
    ytd_gross: Decimal | int | str,
    month: int,
    prior_year: int | None = None,
) -> list[Nudge]:
    """Produce the nudges for the given YTD snapshot.

    Inputs:
      - `user_nin_hash`: taxpayer identity key (may be None for anonymous dev).
      - `current_year`: the year the YTD is inside.
      - `ytd_gross`: naira earned so far in the year.
      - `month`: 1-12, the month the YTD is through (used to annualize).
      - `prior_year`: defaults to current_year - 1.
    """
    prior_year = prior_year if prior_year is not None else current_year - 1
    ytd = _as_decimal(ytd_gross) or Decimal("0")
    annualized = annualize(ytd, month=month).quantize(Decimal("0.01"))

    nudges: list[Nudge] = []

    # --- Historical comparison ----------------------------------------
    prior_gross = _fetch_prior_gross(
        session, user_nin_hash=user_nin_hash, year=prior_year
    )
    if prior_gross is not None and prior_gross > 0:
        delta = (annualized - prior_gross) / prior_gross
        pct = delta * Decimal("100")
        if abs(delta) >= Decimal("0.30"):
            severity: Severity = "watch"
            direction = "up" if delta > 0 else "down"
            nudges.append(
                Nudge(
                    code="YOY_PACE",
                    severity=severity,
                    message=(
                        f"At this pace your {current_year} gross is "
                        f"₦{annualized:,.2f} — {direction} "
                        f"{abs(pct):.1f}% from ₦{prior_gross:,.2f} in "
                        f"{prior_year}. Worth a plan review."
                    ),
                    meta={
                        "annualized_gross": f"{annualized:f}",
                        "prior_gross": f"{prior_gross:f}",
                        "pct_change": f"{delta.quantize(Decimal('0.0001')):f}",
                    },
                )
            )

    # --- PIT band crossing --------------------------------------------
    current_band = _band_for(annualized)
    if prior_gross is not None and prior_gross > 0:
        prior_band = _band_for(prior_gross)
        if current_band.order > prior_band.order:
            nudges.append(
                Nudge(
                    code="PIT_BAND_CROSS",
                    severity="alert",
                    message=(
                        f"Annualized income ₦{annualized:,.2f} moves you from "
                        f"band {prior_band.order} ({prior_band.name}, "
                        f"{prior_band.rate * 100:.0f}%) into band "
                        f"{current_band.order} ({current_band.name}, "
                        f"{current_band.rate * 100:.0f}%). Consider whether "
                        f"a pension top-up can keep marginal income in the "
                        f"lower band."
                    ),
                    meta={
                        "prior_band": prior_band.order,
                        "current_band": current_band.order,
                        "current_rate": f"{current_band.rate:f}",
                    },
                )
            )

    # --- VAT threshold approach ---------------------------------------
    threshold = REGISTRATION_THRESHOLD
    if annualized >= threshold * Decimal("0.80") and annualized < threshold:
        nudges.append(
            Nudge(
                code="VAT_THRESHOLD_APPROACH",
                severity="watch",
                message=(
                    f"Annualized turnover ₦{annualized:,.2f} is within 20% "
                    f"of the ₦{threshold:,.0f} VAT registration threshold. "
                    f"Prepare to register before you cross it."
                ),
                meta={
                    "annualized": f"{annualized:f}",
                    "threshold": f"{threshold:f}",
                    "distance": f"{(threshold - annualized):f}",
                },
            )
        )
    elif annualized >= threshold:
        nudges.append(
            Nudge(
                code="VAT_THRESHOLD_CROSSED",
                severity="alert",
                message=(
                    f"Annualized turnover ₦{annualized:,.2f} crosses the "
                    f"₦{threshold:,.0f} VAT registration threshold. VAT "
                    f"registration is mandatory — do it now to avoid the "
                    f"4% Development Levy exposure."
                ),
                meta={
                    "annualized": f"{annualized:f}",
                    "threshold": f"{threshold:f}",
                },
            )
        )

    return nudges


def _fetch_prior_gross(
    session: Session, *, user_nin_hash: str | None, year: int
) -> Decimal | None:
    q = session.query(YearlyFact).filter(
        YearlyFact.tax_year == year,
        YearlyFact.fact_type == "annual_gross_income",
    )
    if user_nin_hash is not None:
        q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)
    else:
        q = q.filter(YearlyFact.user_nin_hash.is_(None))
    latest = q.order_by(YearlyFact.recorded_at.desc()).first()
    if latest is None:
        return None
    return _as_decimal(latest.value)


def _default_current_year() -> int:
    return date.today().year
