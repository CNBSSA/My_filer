"""Canonical JSON pack builder for corporate (CIT) returns (Phase 9).

Same contract as `filing/serialize.py` for PIT: pure, deterministic,
stable key order, all amounts rendered as strings at kobo precision.
The CIT computation leans on `app.tax.cit.calculate_cit_2026` which in
turn uses the quarantined placeholder `CIT_BANDS_2026` until the owner
confirms the 2026 schedule — callers that gate on production must
`assert_confirmed(CIT_SOURCE)` before generating a submittable pack.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import __version__ as APP_VERSION
from app.filing.corporate_schemas import (
    CITBandLine,
    CITComputation,
    CITReturn,
    ExpenseLine,
    RevenueLine,
)
from app.tax.cit import calculate_cit_2026
from app.tax.statutory.cit_bands import CIT_SOURCE

TWO_PLACES = Decimal("0.01")
RATE_PLACES = Decimal("0.0001")
ZERO = Decimal("0")


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _d(amount: Decimal) -> str:
    return f"{_q(amount):f}"


def _rate(value: Decimal) -> str:
    return f"{value.quantize(RATE_PLACES, rounding=ROUND_HALF_UP):f}"


def _sum_revenues(revenues: list[RevenueLine]) -> Decimal:
    return sum((r.amount for r in revenues), ZERO)


def _sum_expenses(expenses: list[ExpenseLine]) -> Decimal:
    return sum((e.amount for e in expenses), ZERO)


def _effective_turnover(return_: CITReturn) -> Decimal:
    if return_.declared_turnover is not None:
        return return_.declared_turnover
    return _sum_revenues(return_.revenues)


def _effective_profit(return_: CITReturn) -> Decimal:
    if return_.declared_assessable_profit is not None:
        return return_.declared_assessable_profit
    return _sum_revenues(return_.revenues) - _sum_expenses(return_.expenses)


def compute_return_totals(return_: CITReturn) -> CITReturn:
    """Populate aggregates + CIT computation. Non-destructive — returns
    a copy; the service persists model_dump() of the result so the
    authoritative figures land in the DB."""
    total_revenue = _sum_revenues(return_.revenues)
    total_expenses = _sum_expenses(return_.expenses)
    turnover = _effective_turnover(return_)
    profit = _effective_profit(return_)
    if profit < 0:
        # A loss: CIT is 0 for small-tier, otherwise 0 too; compute on 0.
        profit_for_cit = ZERO
    else:
        profit_for_cit = profit

    cit = calculate_cit_2026(
        annual_turnover=turnover,
        assessable_profit=profit_for_cit,
    )

    computation = CITComputation(
        annual_turnover=_q(turnover),
        total_expenses=_q(total_expenses),
        assessable_profit=_q(profit),
        tier=cit.tier,
        cit_rate=cit.cit_rate,
        cit_amount=cit.cit_amount,
        tertiary_rate=cit.tertiary_rate,
        tertiary_amount=cit.tertiary_amount,
        total_payable=cit.total_payable,
        bands=[
            CITBandLine(
                tier=cit.tier,
                rate=cit.cit_rate,
                taxable_amount=_q(profit_for_cit),
                tax_amount=cit.cit_amount,
            )
        ],
        notes=list(cit.notes),
    )

    net_payable = _q(
        cit.total_payable - return_.wht_already_suffered - return_.advance_tax_paid
    )

    return return_.model_copy(
        update={
            "computation": computation,
            "total_revenue": _q(total_revenue),
            "total_expenses": _q(total_expenses),
            "net_payable": net_payable,
        }
    )


def build_canonical_pack(return_: CITReturn) -> dict[str, Any]:
    """Deterministic, ordered pack ready for JSON storage + PDF render."""
    computed = compute_return_totals(return_)
    comp = computed.computation
    assert comp is not None  # compute_return_totals always sets it

    direction: str
    if (computed.net_payable or ZERO) > 0:
        direction = "payable"
    elif (computed.net_payable or ZERO) < 0:
        direction = "refund"
    else:
        direction = "balanced"

    return {
        "pack_version": "mai-filer-cit-v1",
        "app_version": APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "statutory_source": CIT_SOURCE,
        "tax_year": computed.tax_year,
        "period": {
            "start": computed.period_start.isoformat(),
            "end": computed.period_end.isoformat(),
        },
        "taxpayer": {
            "rc_number": computed.taxpayer.rc_number,
            "company_name": computed.taxpayer.company_name,
            "company_type": computed.taxpayer.company_type,
            "tin": computed.taxpayer.tin,
            "registered_address": computed.taxpayer.registered_address,
            "industry": computed.taxpayer.industry,
            "email": computed.taxpayer.email,
            "phone": computed.taxpayer.phone,
            "primary_officer_name": computed.taxpayer.primary_officer_name,
            "primary_officer_nin": (
                # Never surface the raw NIN in the canonical pack.
                "[REDACTED]" if computed.taxpayer.primary_officer_nin else None
            ),
        },
        "revenues": [
            {"label": r.label, "amount": _d(r.amount)} for r in computed.revenues
        ],
        "expenses": [
            {"kind": e.kind, "label": e.label, "amount": _d(e.amount)}
            for e in computed.expenses
        ],
        "computation": {
            "annual_turnover": _d(comp.annual_turnover),
            "total_expenses": _d(comp.total_expenses),
            "assessable_profit": _d(comp.assessable_profit),
            "tier": comp.tier,
            "cit_rate": _rate(comp.cit_rate),
            "cit_amount": _d(comp.cit_amount),
            "tertiary_rate": _rate(comp.tertiary_rate),
            "tertiary_amount": _d(comp.tertiary_amount),
            "total_payable": _d(comp.total_payable),
            "bands": [
                {
                    "tier": b.tier,
                    "rate": _rate(b.rate),
                    "taxable_amount": _d(b.taxable_amount),
                    "tax_amount": _d(b.tax_amount),
                }
                for b in comp.bands
            ],
            "notes": list(comp.notes),
        },
        "settlement": {
            "cit_total_payable": _d(comp.total_payable),
            "wht_already_suffered": _d(computed.wht_already_suffered),
            "advance_tax_paid": _d(computed.advance_tax_paid),
            "net_payable": _d(computed.net_payable or ZERO),
            "direction": direction,
        },
        "summary": {
            "total_revenue": _d(computed.total_revenue or ZERO),
            "total_expenses": _d(computed.total_expenses or ZERO),
            "net_payable": _d(computed.net_payable or ZERO),
        },
        "supporting_document_ids": list(computed.supporting_document_ids),
        "declaration": {
            "affirmed": computed.declaration,
            "statement": (
                "I declare that the information in this CIT return is true, "
                "correct, and complete to the best of my knowledge."
            ),
        },
        "notes": computed.notes,
    }
