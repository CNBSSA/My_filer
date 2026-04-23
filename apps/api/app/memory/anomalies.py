"""Year-over-year anomaly detector (P8.4).

Given a taxpayer's YearlyFact history, flag significant year-on-year
changes on the money-valued fact types. Thresholds are deliberately
conservative for v1 — tune from real data once the owner has a few
hundred filings on record.

All pure — takes a session + nin_hash, queries, returns structured
findings. No side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import YearlyFact

Severity = Literal["info", "watch", "alert"]

# Thresholds for |pct_change|:
#   < WATCH_THRESHOLD  → info, not flagged
#   [WATCH, ALERT)     → watch
#   >= ALERT_THRESHOLD → alert
WATCH_THRESHOLD = Decimal("0.25")  # 25%
ALERT_THRESHOLD = Decimal("0.50")  # 50%

MONEY_FACT_TYPES = frozenset(
    {
        "annual_gross_income",
        "total_deductions",
        "total_tax",
        "chargeable_income",
        "paye_already_withheld",
        "net_payable",
    }
)


@dataclass(frozen=True)
class AnomalyFinding:
    fact_type: str
    severity: Severity
    prior_year: int
    current_year: int
    prior_value: str
    current_value: str
    pct_change: str  # signed, 4dp
    message: str

    def to_dict(self) -> dict:
        return {
            "fact_type": self.fact_type,
            "severity": self.severity,
            "prior_year": self.prior_year,
            "current_year": self.current_year,
            "prior_value": self.prior_value,
            "current_value": self.current_value,
            "pct_change": self.pct_change,
            "message": self.message,
        }


def _as_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _pct_change(prior: Decimal, current: Decimal) -> Decimal | None:
    if prior == 0:
        return None  # can't divide
    return (current - prior) / prior


def _classify(change: Decimal) -> Severity | None:
    mag = abs(change)
    if mag >= ALERT_THRESHOLD:
        return "alert"
    if mag >= WATCH_THRESHOLD:
        return "watch"
    return None


def _message(fact_type: str, prior: Decimal, current: Decimal, pct: Decimal) -> str:
    direction = "up" if current > prior else "down"
    pct_str = f"{abs(pct) * 100:.1f}%"
    return (
        f"{fact_type} is {direction} {pct_str} year-over-year "
        f"(₦{prior:,.2f} → ₦{current:,.2f}). Worth a second look."
    )


def detect_anomalies(
    session: Session,
    *,
    user_nin_hash: str | None,
    current_year: int,
    prior_year: int | None = None,
) -> list[AnomalyFinding]:
    """Compare `current_year` facts against `prior_year` (default: current-1)
    and emit `AnomalyFinding`s for any money-valued fact type whose
    absolute year-on-year change passes WATCH_THRESHOLD."""
    prior_year = prior_year if prior_year is not None else current_year - 1

    def _latest_values(year: int) -> dict[str, Decimal]:
        q = session.query(YearlyFact).filter(YearlyFact.tax_year == year)
        if user_nin_hash is not None:
            q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)
        else:
            q = q.filter(YearlyFact.user_nin_hash.is_(None))
        latest: dict[str, YearlyFact] = {}
        for row in q.order_by(YearlyFact.recorded_at.asc()).all():
            if row.fact_type in MONEY_FACT_TYPES:
                latest[row.fact_type] = row  # last write wins
        return {
            ft: v
            for ft, fact in latest.items()
            if (v := _as_decimal(fact.value)) is not None
        }

    prior = _latest_values(prior_year)
    current = _latest_values(current_year)

    findings: list[AnomalyFinding] = []
    for fact_type in sorted(set(prior) & set(current)):
        p = prior[fact_type]
        c = current[fact_type]
        change = _pct_change(p, c)
        if change is None:
            continue
        severity = _classify(change)
        if severity is None:
            continue
        findings.append(
            AnomalyFinding(
                fact_type=fact_type,
                severity=severity,
                prior_year=prior_year,
                current_year=current_year,
                prior_value=f"{p:f}",
                current_value=f"{c:f}",
                pct_change=f"{change.quantize(Decimal('0.0001')):f}",
                message=_message(fact_type, p, c, change),
            )
        )
    return findings
