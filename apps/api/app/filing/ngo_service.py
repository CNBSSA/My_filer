"""NGO filing service (P11.3).

Thin layer that mirrors `filing/service.py` but works off the NGO
return schema + audit. The PDF + object-storage machinery from Phase 4
is reused via a shared renderer path below so NGO packs get a real
downloadable artefact without a second PDF framework.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Filing
from app.documents.storage import StorageAdapter
from app.filing.ngo_audit import NGOAuditReport, audit as run_ngo_audit
from app.filing.ngo_schemas import NGOReturn
from app.filing.ngo_serialize import build_canonical_pack
from app.filing.pdf import render_pack_pdf
from app.filing.service import PackNotReadyError


def create_ngo_filing(
    *,
    session: Session,
    return_: NGOReturn,
    user_id: str | None = None,
) -> Filing:
    filing = Filing(
        user_id=user_id,
        tax_year=return_.tax_year,
        tax_kind="ngo_annual",
        return_json=return_.model_dump(mode="json"),
        audit_status="pending",
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


def update_ngo_filing(
    *, session: Session, filing: Filing, return_: NGOReturn
) -> Filing:
    filing.return_json = return_.model_dump(mode="json")
    filing.tax_kind = "ngo_annual"
    filing.audit_status = "pending"
    filing.audit_json = None
    filing.pack_pdf_key = None
    filing.pack_json_key = None
    filing.finalized_at = None
    session.commit()
    session.refresh(filing)
    return filing


def audit_ngo_filing(*, session: Session, filing: Filing) -> NGOAuditReport:
    return_ = NGOReturn.model_validate(filing.return_json)
    report = run_ngo_audit(return_)
    filing.audit_status = report.status
    filing.audit_json = report.to_dict()
    session.commit()
    session.refresh(filing)
    return report


def generate_ngo_pack(
    *,
    session: Session,
    storage: StorageAdapter,
    filing: Filing,
) -> dict[str, Any]:
    """Audit + build + persist the NGO pack (JSON + PDF)."""
    report = audit_ngo_filing(session=session, filing=filing)
    if report.status == "red":
        raise PackNotReadyError(
            "Audit Shield returned red — resolve findings before generating the NGO pack."
        )

    return_ = NGOReturn.model_validate(filing.return_json)
    pack = build_canonical_pack(return_)

    json_bytes = json.dumps(pack, ensure_ascii=False, indent=2).encode("utf-8")
    pdf_bytes = _render_ngo_pack_pdf(pack)

    json_blob = storage.put(
        json_bytes,
        content_type="application/json",
        filename=f"ngo-filing-{filing.id}.json",
    )
    pdf_blob = storage.put(
        pdf_bytes,
        content_type="application/pdf",
        filename=f"ngo-filing-{filing.id}.pdf",
    )

    filing.pack_json_key = json_blob.key
    filing.pack_pdf_key = pdf_blob.key
    filing.finalized_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(filing)
    return pack


def _render_ngo_pack_pdf(pack: dict[str, Any]) -> bytes:
    """Shim over the Phase 4 PIT renderer.

    The NGO pack shape differs (no PIT band breakdown, different
    sections). For v1 we lift an organisation-flavoured skeleton into
    the PIT renderer's data contract — good enough for a reviewable
    downloadable PDF. A dedicated NGO renderer lands alongside the
    first NRS-published NGO form template.
    """
    org = pack["organization"]
    summary = pack["summary"]
    income = pack["income"]
    expenditure = pack["expenditure"]

    adapted = {
        "pack_version": pack["pack_version"],
        "app_version": pack["app_version"],
        "generated_at": pack["generated_at"],
        "tax_year": pack["tax_year"],
        "period": pack["period"],
        "taxpayer": {
            "full_name": org["legal_name"],
            "nin": org["cac_part_c_rc"],
            "date_of_birth": None,
            "marital_status": "unknown",
            "residential_address": org["registered_address"],
            "phone": org["phone"],
            "email": org["email"],
        },
        "income": {
            "sources": [],
            "total_gross": summary["total_income"],
        },
        "deductions": {
            "pension": "0.00",
            "nhis": "0.00",
            "cra": "0.00",
            "life_insurance": "0.00",
            "nhf": "0.00",
            "other_reliefs": [
                {"label": "Programme expenditure", "amount": expenditure["program_expenses"]},
                {"label": "Administrative", "amount": expenditure["administrative"]},
                {"label": "Fundraising", "amount": expenditure["fundraising"]},
            ],
            "total": expenditure["total"],
        },
        "computation": {
            "annual_income": summary["total_income"],
            "total_deductions": summary["total_expenditure"],
            "chargeable_income": summary["net_result"],
            "bands": [],
            "total_tax": "0.00",
            "effective_rate": "0.0000",
        },
        "settlement": {
            "paye_already_withheld": summary["total_wht_remitted"],
            "net_payable": "0.00",
            "direction": summary["direction"],
        },
        "declaration": pack["declaration"],
    }
    return render_pack_pdf(adapted)
