"""Canonical JSON pack builder for NGO returns (Phase 11).

Same contract as `filing/serialize.py` for PIT: pure, deterministic,
stable key order, all amounts rendered as strings at kobo precision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import __version__ as APP_VERSION
from app.filing.ngo_schemas import NGOReturn

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _d(amount: Decimal) -> str:
    return f"{_q(amount):f}"


def compute_return_totals(return_: NGOReturn) -> NGOReturn:
    """Return a copy with aggregate fields populated from their atomic
    children. This is the authoritative pass — the UI can compute its
    own preview, but the downloadable pack uses *this* answer."""
    total_income = return_.income.total()
    total_expenditure = return_.expenditure.total()
    total_wht = sum((row.wht_amount for row in return_.wht_schedule), ZERO)
    net = total_income - total_expenditure

    return return_.model_copy(
        update={
            "total_income": _q(total_income),
            "total_expenditure": _q(total_expenditure),
            "total_wht_remitted": _q(total_wht),
            "net_result": _q(net),
        }
    )


def _income_block(ret: NGOReturn) -> dict[str, str]:
    b = ret.income
    return {
        "local_donations": _d(b.local_donations),
        "foreign_donations": _d(b.foreign_donations),
        "government_grants": _d(b.government_grants),
        "foundation_grants": _d(b.foundation_grants),
        "program_income": _d(b.program_income),
        "investment_income": _d(b.investment_income),
        "other_income": _d(b.other_income),
        "total": _d(b.total()),
    }


def _expenditure_block(ret: NGOReturn) -> dict[str, str]:
    b = ret.expenditure
    return {
        "program_expenses": _d(b.program_expenses),
        "administrative": _d(b.administrative),
        "fundraising": _d(b.fundraising),
        "other": _d(b.other),
        "total": _d(b.total()),
    }


def build_canonical_pack(return_: NGOReturn) -> dict[str, Any]:
    """Build the ordered NGO-flavoured pack."""
    computed = compute_return_totals(return_)

    return {
        "pack_version": "mai-filer-ngo-v1",
        "app_version": APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tax_year": computed.tax_year,
        "period": {
            "start": computed.period_start.isoformat(),
            "end": computed.period_end.isoformat(),
        },
        "organization": {
            "cac_part_c_rc": computed.organization.cac_part_c_rc,
            "legal_name": computed.organization.legal_name,
            "trade_name": computed.organization.trade_name,
            "exemption_reference": computed.organization.exemption_reference,
            "purpose": computed.organization.purpose,
            "registered_address": computed.organization.registered_address,
            "email": computed.organization.email,
            "phone": computed.organization.phone,
        },
        "income": _income_block(computed),
        "expenditure": _expenditure_block(computed),
        "wht_schedule": [
            {
                "period_month": row.period_month,
                "transaction_class": row.transaction_class,
                "recipient_category": row.recipient_category,
                "gross_amount": _d(row.gross_amount),
                "wht_amount": _d(row.wht_amount),
                "recipient_reference": row.recipient_reference,
                "remittance_receipt": row.remittance_receipt,
            }
            for row in computed.wht_schedule
        ],
        "summary": {
            "total_income": _d(computed.total_income or ZERO),
            "total_expenditure": _d(computed.total_expenditure or ZERO),
            "total_wht_remitted": _d(computed.total_wht_remitted or ZERO),
            "net_result": _d(computed.net_result or ZERO),
            "direction": (
                "surplus"
                if (computed.net_result or ZERO) > 0
                else ("deficit" if (computed.net_result or ZERO) < 0 else "balanced")
            ),
        },
        "supporting_document_ids": list(computed.supporting_document_ids),
        "exemption_status_declaration": {
            "affirmed": computed.exemption_status_declaration,
            "statement": (
                "The trustees affirm that the organisation continues to meet "
                "the criteria for tax-exempt status for this tax year."
            ),
        },
        "declaration": {
            "affirmed": computed.declaration,
            "statement": (
                "I declare that the information in this NGO annual return is "
                "true, correct, and complete to the best of my knowledge."
            ),
        },
        "notes": computed.notes,
    }
