"""Filing service (P4.4a) — create, audit, and generate the pack.

The service layer keeps the router thin and reuses the same functions for
Mai Filer's tools. All persistence goes through the provided `Session`;
generated PDF + JSON packs are persisted to the object storage adapter
under stable keys (`filings/<id>/pack.pdf`, `filings/<id>/pack.json`).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Filing
from app.documents.storage import StorageAdapter
from app.filing.audit import AuditReport, audit
from app.filing.pdf import render_pack_pdf
from app.filing.schemas import PITReturn
from app.filing.serialize import build_canonical_pack


def create_filing(
    *,
    session: Session,
    return_: PITReturn,
    user_id: str | None = None,
) -> Filing:
    filing = Filing(
        user_id=user_id,
        tax_year=return_.tax_year,
        return_json=return_.model_dump(mode="json"),
        audit_status="pending",
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


def update_filing_return(
    *, session: Session, filing: Filing, return_: PITReturn
) -> Filing:
    filing.return_json = return_.model_dump(mode="json")
    filing.audit_status = "pending"
    filing.audit_json = None
    filing.pack_pdf_key = None
    filing.pack_json_key = None
    filing.finalized_at = None
    session.commit()
    session.refresh(filing)
    return filing


def audit_filing(*, session: Session, filing: Filing) -> AuditReport:
    return_ = PITReturn.model_validate(filing.return_json)
    report = audit(return_)
    filing.audit_status = report.status
    filing.audit_json = report.to_dict()
    session.commit()
    session.refresh(filing)
    return report


class PackNotReadyError(RuntimeError):
    """Raised when a pack is requested but the return hasn't passed Audit Shield."""


def generate_pack(
    *,
    session: Session,
    storage: StorageAdapter,
    filing: Filing,
) -> dict[str, Any]:
    """Run Audit Shield, then (if green) build + persist the JSON and PDF pack.

    Returns the canonical pack dict. The PDF storage key is stashed on the
    filing row so downloads can stream it.
    """
    report = audit_filing(session=session, filing=filing)
    if report.status == "red":
        raise PackNotReadyError(
            "Audit Shield returned red — resolve findings before generating the pack."
        )

    return_ = PITReturn.model_validate(filing.return_json)
    pack = build_canonical_pack(return_)

    json_bytes = json.dumps(pack, ensure_ascii=False, indent=2).encode("utf-8")
    pdf_bytes = render_pack_pdf(pack)

    json_blob = storage.put(
        json_bytes, content_type="application/json", filename=f"filing-{filing.id}.json"
    )
    pdf_blob = storage.put(
        pdf_bytes, content_type="application/pdf", filename=f"filing-{filing.id}.pdf"
    )

    filing.pack_json_key = json_blob.key
    filing.pack_pdf_key = pdf_blob.key
    filing.finalized_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(filing)

    return pack


def load_pack_bytes(
    *, storage: StorageAdapter, filing: Filing, format: str
) -> tuple[bytes, str, str]:
    """Fetch the persisted pack (PDF or JSON). Returns (bytes, content_type, filename)."""
    if format == "pdf":
        if not filing.pack_pdf_key:
            raise PackNotReadyError("PDF pack has not been generated yet.")
        return (
            storage.get(filing.pack_pdf_key),
            "application/pdf",
            f"mai-filer-pit-{filing.tax_year}-{filing.id}.pdf",
        )
    if format == "json":
        if not filing.pack_json_key:
            raise PackNotReadyError("JSON pack has not been generated yet.")
        return (
            storage.get(filing.pack_json_key),
            "application/json",
            f"mai-filer-pit-{filing.tax_year}-{filing.id}.json",
        )
    raise ValueError(f"unsupported pack format: {format}")
