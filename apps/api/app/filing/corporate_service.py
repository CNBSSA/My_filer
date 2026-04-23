"""Corporate (CIT) filing service (Phase 9).

Mirrors `filing/service.py` (PIT) and `filing/ngo_service.py` (NGO):

  1. create_corporate_filing → persist as a Filing with tax_kind="cit"
  2. update_corporate_filing → same row, resets audit + pack state
  3. audit_corporate_filing → run Audit Shield, persist report
  4. generate_corporate_pack → audit + canonical JSON pack + PDF to storage

The PDF is rendered via the Phase 4 PIT renderer through a data shim
(same pattern as the NGO pack) so corporate filings get a real
downloadable artefact without a second PDF framework. A dedicated
corporate renderer lands once NRS publishes the CIT form template and
the 2026 statutory bands are confirmed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Filing
from app.documents.storage import StorageAdapter
from app.filing.corporate_audit import (
    CorporateAuditReport,
    audit as run_corporate_audit,
)
from app.filing.corporate_schemas import CITReturn
from app.filing.corporate_serialize import build_canonical_pack
from app.filing.pdf import render_pack_pdf
from app.filing.service import PackNotReadyError


def create_corporate_filing(
    *,
    session: Session,
    return_: CITReturn,
    user_id: str | None = None,
) -> Filing:
    filing = Filing(
        user_id=user_id,
        tax_year=return_.tax_year,
        tax_kind="cit",
        return_json=return_.model_dump(mode="json"),
        audit_status="pending",
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


def update_corporate_filing(
    *, session: Session, filing: Filing, return_: CITReturn
) -> Filing:
    filing.return_json = return_.model_dump(mode="json")
    filing.tax_kind = "cit"
    filing.audit_status = "pending"
    filing.audit_json = None
    filing.pack_pdf_key = None
    filing.pack_json_key = None
    filing.finalized_at = None
    session.commit()
    session.refresh(filing)
    return filing


def audit_corporate_filing(
    *, session: Session, filing: Filing
) -> CorporateAuditReport:
    return_ = CITReturn.model_validate(filing.return_json)
    report = run_corporate_audit(return_)
    filing.audit_status = report.status
    filing.audit_json = report.to_dict()
    session.commit()
    session.refresh(filing)
    return report


def generate_corporate_pack(
    *,
    session: Session,
    storage: StorageAdapter,
    filing: Filing,
) -> dict[str, Any]:
    report = audit_corporate_filing(session=session, filing=filing)
    if report.status == "red":
        raise PackNotReadyError(
            "Audit Shield returned red — resolve findings before generating the CIT pack."
        )

    return_ = CITReturn.model_validate(filing.return_json)
    pack = build_canonical_pack(return_)

    json_bytes = json.dumps(pack, ensure_ascii=False, indent=2).encode("utf-8")
    pdf_bytes = _render_corporate_pack_pdf(pack)

    json_blob = storage.put(
        json_bytes,
        content_type="application/json",
        filename=f"cit-filing-{filing.id}.json",
    )
    pdf_blob = storage.put(
        pdf_bytes,
        content_type="application/pdf",
        filename=f"cit-filing-{filing.id}.pdf",
    )

    filing.pack_json_key = json_blob.key
    filing.pack_pdf_key = pdf_blob.key
    filing.finalized_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(filing)
    return pack


def _render_corporate_pack_pdf(pack: dict[str, Any]) -> bytes:
    """Shim the CIT pack into the Phase 4 PIT PDF renderer's data shape.

    The layout is close enough — header + taxpayer block + a figures
    table + settlement + declaration. A dedicated renderer can replace
    this once the NRS CIT form template is confirmed.
    """
    tp = pack["taxpayer"]
    comp = pack["computation"]
    settlement = pack["settlement"]
    summary = pack["summary"]

    expense_items = [
        {"label": f"{e['kind']}: {e['label']}", "amount": e["amount"]}
        for e in pack["expenses"]
    ]

    adapted = {
        "pack_version": pack["pack_version"],
        "app_version": pack["app_version"],
        "generated_at": pack["generated_at"],
        "tax_year": pack["tax_year"],
        "period": pack["period"],
        "taxpayer": {
            "full_name": tp["company_name"],
            "nin": tp["rc_number"],
            "date_of_birth": None,
            "marital_status": "unknown",
            "residential_address": tp["registered_address"],
            "phone": tp["phone"],
            "email": tp["email"],
        },
        "income": {
            "sources": [
                {
                    "kind": "corporate_revenue",
                    "payer_name": r["label"],
                    "gross_amount": r["amount"],
                    "tax_withheld": "0.00",
                    "period_start": pack["period"]["start"],
                    "period_end": pack["period"]["end"],
                }
                for r in pack["revenues"]
            ],
            "total_gross": summary["total_revenue"],
        },
        "deductions": {
            "pension": "0.00",
            "nhis": "0.00",
            "cra": "0.00",
            "life_insurance": "0.00",
            "nhf": "0.00",
            "other_reliefs": expense_items,
            "total": summary["total_expenses"],
        },
        "computation": {
            "annual_income": comp["annual_turnover"],
            "total_deductions": comp["total_expenses"],
            "chargeable_income": comp["assessable_profit"],
            "bands": [
                {
                    "order": idx + 1,
                    "name": f"Tier: {b['tier']}",
                    "rate": b["rate"],
                    "taxable_amount": b["taxable_amount"],
                    "tax_amount": b["tax_amount"],
                }
                for idx, b in enumerate(comp["bands"])
            ],
            "total_tax": comp["total_payable"],
            "effective_rate": comp["cit_rate"],
        },
        "settlement": {
            "paye_already_withheld": settlement["wht_already_suffered"],
            "net_payable": settlement["net_payable"],
            "direction": settlement["direction"],
        },
        "declaration": pack["declaration"],
    }
    return render_pack_pdf(adapted)
