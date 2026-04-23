"""SME endpoints — thin HTTP surface over the Phase 9 calculators.

Phase 9 is blocked on owner-supplied statutory tables (see
`apps/api/app/tax/statutory/` + ADR-0005). These endpoints exist so the
web SME page can exercise CIT / WHT / UBL validation today against the
placeholder tables. Every response surfaces
`statutory_is_placeholder: true` so the UI can render a prominent
"illustrative data — not for production filing" banner.

Creation of a persisted corporate `Filing` lands when the statutory
tables are confirmed; this surface is read-only by design for now.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.filing.ubl import UBLEnvelope, validate_envelope
from app.tax.cit import calculate_cit_2026
from app.tax.statutory import CIT_SOURCE, UBL_SOURCE, WHT_SOURCE, is_placeholder
from app.tax.wht import calculate_wht, known_transaction_classes

router = APIRouter(prefix="/v1/sme", tags=["sme"])


def _d(amount: Decimal) -> str:
    return f"{amount:f}"


class CITRequest(BaseModel):
    annual_turnover: Decimal = Field(ge=Decimal("0"))
    assessable_profit: Decimal = Field(ge=Decimal("0"))
    include_tertiary: bool = True


@router.post("/calc-cit")
async def calc_cit(body: CITRequest) -> dict[str, Any]:
    result = calculate_cit_2026(
        annual_turnover=body.annual_turnover,
        assessable_profit=body.assessable_profit,
        include_tertiary=body.include_tertiary,
    )
    return {
        "annual_turnover": _d(result.annual_turnover),
        "assessable_profit": _d(result.assessable_profit),
        "tier": result.tier,
        "cit_rate": _d(result.cit_rate),
        "cit_amount": _d(result.cit_amount),
        "tertiary_rate": _d(result.tertiary_rate),
        "tertiary_amount": _d(result.tertiary_amount),
        "total_payable": _d(result.total_payable),
        "notes": list(result.notes),
        "statutory_source": CIT_SOURCE,
        "statutory_is_placeholder": is_placeholder(CIT_SOURCE),
    }


class WHTRequest(BaseModel):
    gross_amount: Decimal = Field(ge=Decimal("0"))
    transaction_class: str = Field(min_length=1, max_length=64)


@router.post("/calc-wht")
async def calc_wht(body: WHTRequest) -> dict[str, Any]:
    try:
        result = calculate_wht(
            gross_amount=body.gross_amount,
            transaction_class=body.transaction_class,
        )
    except ValueError as exc:
        return {
            "error": str(exc),
            "known_classes": known_transaction_classes(),
            "statutory_source": WHT_SOURCE,
            "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
        }
    return {
        "transaction_class": result.transaction_class,
        "gross_amount": _d(result.gross_amount),
        "wht_rate": _d(result.wht_rate),
        "wht_amount": _d(result.wht_amount),
        "net_payable": _d(result.net_payable),
        "statutory_source": WHT_SOURCE,
        "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
    }


@router.get("/wht-classes")
async def list_wht_classes_endpoint() -> dict[str, Any]:
    return {
        "classes": known_transaction_classes(),
        "statutory_source": WHT_SOURCE,
        "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
    }


class UBLValidateRequest(BaseModel):
    envelope: dict[str, Any]


@router.post("/validate-ubl")
async def validate_ubl(body: UBLValidateRequest) -> dict[str, Any]:
    try:
        typed = UBLEnvelope.model_validate(body.envelope)
    except Exception as exc:
        return {
            "error": f"envelope failed schema parse: {exc}",
            "statutory_source": UBL_SOURCE,
            "statutory_is_placeholder": is_placeholder(UBL_SOURCE),
        }
    report = validate_envelope(typed)
    payload = report.to_dict()
    payload["statutory_source"] = UBL_SOURCE
    payload["statutory_is_placeholder"] = is_placeholder(UBL_SOURCE)
    return payload
