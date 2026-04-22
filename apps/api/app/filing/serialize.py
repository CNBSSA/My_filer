"""Canonical JSON pack builder (P4.2).

Given a `PITReturn` we compute (or recompute) the authoritative figures and
emit a stable, ordered JSON pack suitable for:
  - Audit Shield (re-validation upstream of the live NRS gateway).
  - Manual submission via the NRS self-service portal.
  - Storage in Postgres as a point-in-time immutable record.

Rules:
  * Pure functional — same input, same output.
  * No Decimal floats; all amounts rendered as strings with kobo precision.
  * Key order is locked so two packs with identical contents are
    byte-identical after `json.dumps(sort_keys=False)`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app import __version__ as APP_VERSION
from app.filing.schemas import (
    Deductions,
    IncomeSource,
    PITBandLine,
    PITComputation,
    PITReturn,
)
from app.tax.paye import calculate_paye

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")
RATE_PLACES = Decimal("0.0001")


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _d(amount: Decimal) -> str:
    """Stringify a Decimal at kobo precision, positional (no scientific)."""
    return f"{_q(amount):f}"


def _total_gross(sources: list[IncomeSource]) -> Decimal:
    return sum((s.gross_amount for s in sources), ZERO)


def _total_withheld(sources: list[IncomeSource]) -> Decimal:
    return sum((s.tax_withheld for s in sources), ZERO)


def compute_return_totals(return_: PITReturn) -> PITReturn:
    """Return a copy with `computation`, `total_gross_income`, and `net_payable`
    recomputed from the income + deductions blocks. This is the
    authoritative pass — the UI may compute its own preview, but the pack
    uses *this* answer."""
    gross = _total_gross(return_.income_sources)
    deductions = return_.deductions
    paye_withheld_total = return_.paye_already_withheld
    if paye_withheld_total == ZERO:
        paye_withheld_total = _total_withheld(return_.income_sources)

    paye = calculate_paye(
        gross,
        pension=deductions.pension,
        nhis=deductions.nhis,
        cra=deductions.cra,
        other_reliefs=(
            deductions.life_insurance
            + deductions.nhf
            + sum((li.amount for li in deductions.other_reliefs), ZERO)
        ),
    )

    bands = [
        PITBandLine(
            order=b.band.order,
            name=b.band.name,
            rate=b.band.rate,
            taxable_amount=b.taxable_amount,
            tax_amount=b.tax_amount,
        )
        for b in paye.pit.bands
    ]

    computation = PITComputation(
        annual_income=_q(gross),
        total_deductions=_q(deductions.total()),
        chargeable_income=_q(paye.chargeable_income),
        bands=bands,
        total_tax=_q(paye.annual_tax),
        effective_rate=paye.pit.effective_rate.quantize(RATE_PLACES, rounding=ROUND_HALF_UP),
    )

    net_payable = _q(paye.annual_tax - paye_withheld_total)

    return return_.model_copy(
        update={
            "computation": computation,
            "total_gross_income": _q(gross),
            "paye_already_withheld": _q(paye_withheld_total),
            "net_payable": net_payable,
        }
    )


def _deductions_block(d: Deductions) -> dict[str, Any]:
    return {
        "pension": _d(d.pension),
        "nhis": _d(d.nhis),
        "cra": _d(d.cra),
        "life_insurance": _d(d.life_insurance),
        "nhf": _d(d.nhf),
        "other_reliefs": [
            {"label": li.label, "amount": _d(li.amount)} for li in d.other_reliefs
        ],
        "total": _d(d.total()),
    }


def build_canonical_pack(return_: PITReturn) -> dict[str, Any]:
    """Build the ordered, stable JSON pack from a (possibly partially-filled)
    return. `compute_return_totals` is run first so the pack is always
    authoritative."""
    computed = compute_return_totals(return_)
    assert computed.computation is not None  # satisfied by compute_return_totals

    return {
        "pack_version": "mai-filer-pit-v1",
        "app_version": APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tax_year": computed.tax_year,
        "period": {
            "start": computed.period_start.isoformat(),
            "end": computed.period_end.isoformat(),
        },
        "taxpayer": {
            "nin": computed.taxpayer.nin,
            "full_name": computed.taxpayer.full_name,
            "date_of_birth": (
                computed.taxpayer.date_of_birth.isoformat()
                if computed.taxpayer.date_of_birth
                else None
            ),
            "marital_status": computed.taxpayer.marital_status,
            "residential_address": computed.taxpayer.residential_address,
            "phone": computed.taxpayer.phone,
            "email": computed.taxpayer.email,
        },
        "income": {
            "sources": [
                {
                    "kind": s.kind,
                    "payer_name": s.payer_name,
                    "gross_amount": _d(s.gross_amount),
                    "tax_withheld": _d(s.tax_withheld),
                    "period_start": s.period_start.isoformat(),
                    "period_end": s.period_end.isoformat(),
                    "supporting_document_id": s.supporting_document_id,
                }
                for s in computed.income_sources
            ],
            "total_gross": _d(computed.total_gross_income or ZERO),
        },
        "deductions": _deductions_block(computed.deductions),
        "computation": {
            "annual_income": _d(computed.computation.annual_income),
            "total_deductions": _d(computed.computation.total_deductions),
            "chargeable_income": _d(computed.computation.chargeable_income),
            "bands": [
                {
                    "order": b.order,
                    "name": b.name,
                    "rate": _d(b.rate),
                    "taxable_amount": _d(b.taxable_amount),
                    "tax_amount": _d(b.tax_amount),
                }
                for b in computed.computation.bands
            ],
            "total_tax": _d(computed.computation.total_tax),
            "effective_rate": f"{computed.computation.effective_rate:f}",
        },
        "settlement": {
            "paye_already_withheld": _d(computed.paye_already_withheld),
            "net_payable": _d(computed.net_payable or ZERO),
            "direction": "payable" if (computed.net_payable or ZERO) > 0 else (
                "refund" if (computed.net_payable or ZERO) < 0 else "balanced"
            ),
        },
        "supporting_document_ids": list(computed.supporting_document_ids),
        "declaration": {
            "affirmed": computed.declaration,
            "statement": (
                "I declare that the information provided in this return is true, "
                "correct, and complete to the best of my knowledge."
            ),
        },
        "notes": computed.notes,
    }
