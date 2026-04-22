"""Development Levy — 4% on assessable profits of large corporations.

Scaffolded in v1 for shape only. The full Dev Levy workflow (who qualifies
as "large", assessment method, timing) is v2 / Phase 9 per ADR-0002.

If Mai Filer ever calls this in v1 (e.g. a PAYE user asks about it), the
function returns the straight 4% math and nothing else; the agent is
expected to caveat that Dev Levy is corporate, not individual, and deep
corporate logic is not yet in scope.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DEV_LEVY_RATE = Decimal("0.04")
TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def _to_decimal(value: Decimal | int | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def calculate_dev_levy(assessable_profit: Decimal | int | str) -> Decimal:
    """4% of assessable profit, floored at zero, rounded to kobo."""
    profit = _to_decimal(assessable_profit)
    if profit <= ZERO:
        return Decimal("0.00")
    return (profit * DEV_LEVY_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
