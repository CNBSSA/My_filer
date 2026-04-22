"""Reliefs exploration — Mai Filer's Calculator & Optimizer (Role 3).

This module does *not* enforce statutory relief caps (they are not yet locked
in our Knowledge Base for 2026); it computes what-if scenarios so the agent
can show the user the marginal savings of adding ₦X of pension top-up, life
insurance, or other allowable reliefs.

Input: a PAYE baseline + a list of candidate reliefs.
Output: each scenario's new chargeable income, new PAYE, and the delta.

Mai Filer must present these as *suggestions* and cite that the final
deductibility check belongs to the user's employer / the NRS — not to us.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.tax.paye import PAYEResult, calculate_paye

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class ReliefScenario:
    """A what-if: 'what if I added ₦amount to this relief category?'"""

    category: str  # e.g. "pension_topup", "life_insurance", "nhf"
    amount: Decimal

    def describe(self) -> str:
        return f"{self.category}:+₦{self.amount:,}"


@dataclass(frozen=True)
class ReliefOutcome:
    scenario: ReliefScenario
    baseline_tax: Decimal
    projected_tax: Decimal
    tax_saved: Decimal
    projected_chargeable: Decimal


def _to_decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def explore_reliefs(
    annual_gross: Decimal | int | str,
    *,
    baseline_pension: Decimal | int | str = ZERO,
    baseline_nhis: Decimal | int | str = ZERO,
    baseline_cra: Decimal | int | str = ZERO,
    baseline_other_reliefs: Decimal | int | str = ZERO,
    scenarios: list[ReliefScenario] | None = None,
) -> tuple[PAYEResult, list[ReliefOutcome]]:
    """Compute the baseline PAYE and a PAYE projection per relief scenario.

    Returns `(baseline, [ReliefOutcome, ...])`.

    Each scenario is applied *additively* to the relevant baseline input:
      - `pension_topup` → adds to `pension`
      - `life_insurance` / `nhf` / any other category → adds to `other_reliefs`

    This keeps the surface small; as statutory categories are locked in
    the Knowledge Base we can introduce category-specific routing.
    """
    baseline = calculate_paye(
        annual_gross,
        pension=baseline_pension,
        nhis=baseline_nhis,
        cra=baseline_cra,
        other_reliefs=baseline_other_reliefs,
    )

    outcomes: list[ReliefOutcome] = []
    for scenario in scenarios or []:
        if scenario.amount < ZERO:
            raise ValueError(f"scenario amount must be >= 0: {scenario.describe()}")

        extra_pension = scenario.amount if scenario.category == "pension_topup" else ZERO
        extra_other = scenario.amount if scenario.category != "pension_topup" else ZERO

        projected = calculate_paye(
            annual_gross,
            pension=_to_decimal(baseline_pension) + extra_pension,
            nhis=_to_decimal(baseline_nhis),
            cra=_to_decimal(baseline_cra),
            other_reliefs=_to_decimal(baseline_other_reliefs) + extra_other,
        )

        saved = _q(baseline.annual_tax - projected.annual_tax)
        outcomes.append(
            ReliefOutcome(
                scenario=scenario,
                baseline_tax=baseline.annual_tax,
                projected_tax=projected.annual_tax,
                tax_saved=saved,
                projected_chargeable=projected.chargeable_income,
            )
        )

    return baseline, outcomes
