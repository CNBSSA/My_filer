"""Mid-year nudge tests (P8.5)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.memory.facts import record_fact
from app.memory.nudges import annualize, suggest_nudges

pytestmark = pytest.mark.usefixtures("override_db")


def _seed_prior_gross(db_session, year: int, amount: Decimal) -> None:
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=year,
        fact_type="annual_gross_income",
        value=amount,
    )


def test_annualize_halfway_through_the_year() -> None:
    assert annualize(Decimal("2500000"), month=6) == Decimal("5000000")


def test_annualize_clamps_month() -> None:
    # Before month 1 or past month 12 should not explode.
    assert annualize(Decimal("1000000"), month=0) == Decimal("12000000")
    assert annualize(Decimal("12000000"), month=13) == Decimal("12000000")


def test_suggests_yoy_pace_watch_when_annualized_jumps(db_session) -> None:
    _seed_prior_gross(db_session, 2025, Decimal("5000000"))
    db_session.commit()
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("4000000"),  # annualizes to 8m
        month=6,
    )
    codes = {n.code for n in nudges}
    assert "YOY_PACE" in codes


def test_suggests_pit_band_cross_alert(db_session) -> None:
    # Prior gross sits firmly inside band 2 (under ₦3m).
    _seed_prior_gross(db_session, 2025, Decimal("2500000"))
    db_session.commit()
    # YTD ₦2.5m through month 3 annualizes to ₦10m — band 3.
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("2500000"),
        month=3,
    )
    codes = {n.code for n in nudges}
    assert "PIT_BAND_CROSS" in codes
    band_nudge = next(n for n in nudges if n.code == "PIT_BAND_CROSS")
    assert band_nudge.severity == "alert"


def test_vat_threshold_approach_is_watch(db_session) -> None:
    # Annualizes to ₦84m — within 20% of ₦100m.
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("42000000"),
        month=6,
    )
    codes = {n.code for n in nudges}
    assert "VAT_THRESHOLD_APPROACH" in codes


def test_vat_threshold_crossed_is_alert(db_session) -> None:
    # Annualizes to ₦120m — past the ₦100m threshold.
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("60000000"),
        month=6,
    )
    codes = {n.code for n in nudges}
    assert "VAT_THRESHOLD_CROSSED" in codes


def test_no_nudges_when_on_pace_and_below_thresholds(db_session) -> None:
    _seed_prior_gross(db_session, 2025, Decimal("5000000"))
    db_session.commit()
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("2500000"),  # annualizes to 5m, flat
        month=6,
    )
    assert nudges == []


def test_zero_prior_gross_does_not_divide_by_zero(db_session) -> None:
    _seed_prior_gross(db_session, 2025, Decimal("0"))
    db_session.commit()
    nudges = suggest_nudges(
        db_session,
        user_nin_hash="h",
        current_year=2026,
        ytd_gross=Decimal("2500000"),
        month=6,
    )
    codes = {n.code for n in nudges}
    # No YoY pace nudge (we can't compute a percent from zero).
    assert "YOY_PACE" not in codes
