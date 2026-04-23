"""YoY anomaly detector tests (P8.4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.memory.anomalies import (
    ALERT_THRESHOLD,
    WATCH_THRESHOLD,
    detect_anomalies,
)
from app.memory.facts import record_fact

pytestmark = pytest.mark.usefixtures("override_db")


def _put(db_session, year: int, fact_type: str, value: Decimal) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=year,
        fact_type=fact_type,
        value=value,
    )


def test_no_findings_when_year_missing(db_session) -> None:
    _put(db_session, 2025, "annual_gross_income", Decimal("5000000"))
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert findings == []


def test_small_delta_emits_nothing(db_session) -> None:
    _put(db_session, 2025, "annual_gross_income", Decimal("5000000"))
    _put(db_session, 2026, "annual_gross_income", Decimal("5100000"))  # +2%
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert findings == []


def test_30_percent_increase_is_watch(db_session) -> None:
    _put(db_session, 2025, "annual_gross_income", Decimal("5000000"))
    _put(db_session, 2026, "annual_gross_income", Decimal("6500000"))  # +30%
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert len(findings) == 1
    assert findings[0].fact_type == "annual_gross_income"
    assert findings[0].severity == "watch"
    assert "up 30.0%" in findings[0].message


def test_100_percent_jump_is_alert(db_session) -> None:
    _put(db_session, 2025, "annual_gross_income", Decimal("5000000"))
    _put(db_session, 2026, "annual_gross_income", Decimal("10000000"))  # +100%
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert findings[0].severity == "alert"
    assert "up 100.0%" in findings[0].message


def test_drop_is_reported_as_down(db_session) -> None:
    _put(db_session, 2025, "annual_gross_income", Decimal("10000000"))
    _put(db_session, 2026, "annual_gross_income", Decimal("4000000"))  # -60%
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert findings[0].severity == "alert"
    assert "down 60.0%" in findings[0].message


def test_thresholds_are_correctly_classed() -> None:
    assert WATCH_THRESHOLD == Decimal("0.25")
    assert ALERT_THRESHOLD == Decimal("0.50")


def test_only_money_fact_types_are_compared(db_session) -> None:
    # income_source_count is not in the MONEY_FACT_TYPES set.
    _put(db_session, 2025, "income_source_count", Decimal("1"))
    _put(db_session, 2026, "income_source_count", Decimal("5"))
    db_session.commit()
    findings = detect_anomalies(db_session, user_nin_hash="h", current_year=2026)
    assert findings == []


def test_prior_year_is_customizable(db_session) -> None:
    _put(db_session, 2023, "total_tax", Decimal("500000"))
    _put(db_session, 2026, "total_tax", Decimal("1000000"))
    db_session.commit()
    findings = detect_anomalies(
        db_session, user_nin_hash="h", current_year=2026, prior_year=2023
    )
    assert len(findings) == 1
    assert findings[0].prior_year == 2023
