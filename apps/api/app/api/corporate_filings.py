"""Corporate (CIT) filings router (Phase 9).

Shares the underlying `Filing` row with PIT + NGO; every endpoint
enforces `tax_kind='cit'` so a PUT against the wrong kind 400s rather
than silently corrupting the return_json shape.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.models import Filing
from app.db.session import get_session
from app.documents.storage import StorageAdapter, get_default_storage
from app.filing.corporate_schemas import CITReturn
from app.filing.corporate_service import (
    audit_corporate_filing,
    create_corporate_filing,
    generate_corporate_pack,
    update_corporate_filing,
)
from app.filing.service import PackNotReadyError, load_pack_bytes

router = APIRouter(prefix="/v1/corporate-filings", tags=["corporate"])


def get_storage() -> StorageAdapter:
    return get_default_storage()


def _assert_cit(filing: Filing) -> None:
    if filing.tax_kind != "cit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"filing {filing.id} is tax_kind={filing.tax_kind!r}; "
                "use the corresponding endpoint instead."
            ),
        )


def _load(session: Session, filing_id: str) -> Filing:
    filing = session.get(Filing, filing_id)
    if filing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="filing not found"
        )
    return filing


def _filing_to_dict(filing: Filing) -> dict[str, Any]:
    return {
        "id": filing.id,
        "user_id": filing.user_id,
        "tax_year": filing.tax_year,
        "tax_kind": filing.tax_kind,
        "return": filing.return_json,
        "audit_status": filing.audit_status,
        "audit": filing.audit_json,
        "pack_ready": bool(filing.pack_pdf_key and filing.pack_json_key),
        "finalized_at": filing.finalized_at.isoformat() if filing.finalized_at else None,
        "created_at": filing.created_at.isoformat(),
        "updated_at": filing.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    return_: CITReturn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = create_corporate_filing(session=session, return_=return_)
    return _filing_to_dict(filing)


@router.get("/{filing_id}")
async def read(
    filing_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    return _filing_to_dict(filing)


@router.put("/{filing_id}")
async def update(
    filing_id: str,
    return_: CITReturn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    update_corporate_filing(session=session, filing=filing, return_=return_)
    return _filing_to_dict(filing)


@router.post("/{filing_id}/audit")
async def run_audit(
    filing_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    report = audit_corporate_filing(session=session, filing=filing)
    return {"filing": _filing_to_dict(filing), "audit": report.to_dict()}


@router.post("/{filing_id}/pack")
async def build_pack(
    filing_id: str,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    try:
        pack = generate_corporate_pack(
            session=session, storage=storage, filing=filing
        )
    except PackNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return {"filing": _filing_to_dict(filing), "pack": pack}


@router.get("/{filing_id}/pack.pdf")
async def download_pdf(
    filing_id: str,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
) -> Response:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    try:
        body, content_type, filename = load_pack_bytes(
            storage=storage, filing=filing, format="pdf"
        )
    except PackNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{filing_id}/pack.json")
async def download_json(
    filing_id: str,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
) -> Response:
    filing = _load(session, filing_id)
    _assert_cit(filing)
    try:
        body, content_type, filename = load_pack_bytes(
            storage=storage, filing=filing, format="json"
        )
    except PackNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
