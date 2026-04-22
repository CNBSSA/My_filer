"""Relief exploration tests (P2.6)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.tax.reliefs import ReliefScenario, explore_reliefs


def test_empty_scenarios_return_baseline_only() -> None:
    baseline, outcomes = explore_reliefs(5_000_000)
    assert outcomes == []
    assert baseline.annual_tax == Decimal("690000.00")


def test_pension_topup_reduces_tax_at_marginal_band() -> None:
    """At ₦5m gross with no existing deductions, the user's marginal band
    is band 3 (18%). A ₦100,000 pension top-up shifts ₦100k out of band 3
    and saves 18% × 100,000 = ₦18,000."""
    baseline, outcomes = explore_reliefs(
        5_000_000,
        scenarios=[ReliefScenario(category="pension_topup", amount=Decimal("100000"))],
    )
    assert baseline.annual_tax == Decimal("690000.00")
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.scenario.category == "pension_topup"
    assert outcome.tax_saved == Decimal("18000.00")
    assert outcome.projected_chargeable == Decimal("4900000.00")


def test_life_insurance_treated_as_other_relief() -> None:
    _, outcomes = explore_reliefs(
        5_000_000,
        scenarios=[ReliefScenario(category="life_insurance", amount=Decimal("50000"))],
    )
    # 50k out of band 3 (18%) = 9,000 tax saved.
    assert outcomes[0].tax_saved == Decimal("9000.00")


def test_multiple_scenarios_are_evaluated_independently() -> None:
    """Each scenario is a *what-if*, not cumulative."""
    _, outcomes = explore_reliefs(
        5_000_000,
        scenarios=[
            ReliefScenario(category="pension_topup", amount=Decimal("100000")),
            ReliefScenario(category="life_insurance", amount=Decimal("200000")),
        ],
    )
    assert outcomes[0].tax_saved == Decimal("18000.00")
    # 200k × 18% = 36,000.
    assert outcomes[1].tax_saved == Decimal("36000.00")


def test_relief_across_band_boundary() -> None:
    """At ₦3,000,000 gross the user is exactly at the top of band 2 (15%).
    A ₦500,000 pension top-up moves all ₦500k out of band 2 → 15% × 500k =
    ₦75,000 saved."""
    _, outcomes = explore_reliefs(
        3_000_000,
        scenarios=[ReliefScenario(category="pension_topup", amount=Decimal("500000"))],
    )
    assert outcomes[0].tax_saved == Decimal("75000.00")


def test_negative_scenario_amount_raises() -> None:
    with pytest.raises(ValueError):
        explore_reliefs(
            5_000_000,
            scenarios=[ReliefScenario(category="pension_topup", amount=Decimal("-100"))],
        )


def test_relief_with_existing_deductions_compounds_correctly() -> None:
    """If the user already has pension + NHIS + CRA, a new top-up should
    still reduce tax."""
    baseline, outcomes = explore_reliefs(
        5_000_000,
        baseline_pension=400_000,
        baseline_nhis=75_000,
        baseline_cra=1_000_000,
        scenarios=[ReliefScenario(category="pension_topup", amount=Decimal("100000"))],
    )
    # Baseline chargeable = 5m - 1.475m = 3,525,000 → 330k + 0.18*525k = 424,500.
    assert baseline.annual_tax == Decimal("424500.00")
    # With +100k pension → chargeable = 3,425,000 → 330k + 0.18*425k = 406,500.
    assert outcomes[0].projected_tax == Decimal("406500.00")
    assert outcomes[0].tax_saved == Decimal("18000.00")
