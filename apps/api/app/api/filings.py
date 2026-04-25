"""Filings router (P4.4b).

Flow:
  1. POST   /v1/filings                 → create a Filing from a PITReturn
  2. PUT    /v1/filings/{id}            → update the return
  3. POST   /v1/filings/{id}/audit      → run Audit Shield, return the report
  4. POST   /v1/filings/{id}/pack       → build + persist the pack (green/yellow)
  5. GET    /v1/filings/{id}            → read the filing record
  6. GET    /v1/filings/{id}/pack.pdf   → download the PDF
  7. GET    /v1/filings/{id}/pack.json  → download the canonical JSON
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.limits import limiter

from app.db.models import Filing
from app.db.session import get_session
from app.documents.storage import StorageAdapter, get_default_storage
from app.filing.schemas import PITReturn
from app.filing.service import (
    PackNotReadyError,
    audit_filing,
    create_filing,
    generate_pack,
    load_pack_bytes,
    update_filing_return,
)
from app.gateway.service import SubmissionConfigError, submit_filing_to_nrs

router = APIRouter(prefix="/v1/filings", tags=["filings"])


def get_storage() -> StorageAdapter:
    return get_default_storage()


def _filing_to_dict(filing: Filing) -> dict[str, Any]:
    return {
        "id": filing.id,
        "user_id": filing.user_id,
        "tax_year": filing.tax_year,
        "return": filing.return_json,
        "audit_status": filing.audit_status,
        "audit": filing.audit_json,
        "pack_ready": bool(filing.pack_pdf_key and filing.pack_json_key),
        "finalized_at": filing.finalized_at.isoformat() if filing.finalized_at else None,
        "submission": {
            "status": filing.submission_status,
            "irn": filing.nrs_irn,
            "csid": filing.nrs_csid,
            "qr_payload": filing.nrs_qr_payload,
            "error": (
                None
                if not filing.nrs_submission_error
                else _safe_json(filing.nrs_submission_error)
            ),
            "submitted_at": (
                filing.nrs_submitted_at.isoformat() if filing.nrs_submitted_at else None
            ),
        },
        "created_at": filing.created_at.isoformat(),
        "updated_at": filing.updated_at.isoformat(),
    }


def _safe_json(value: str) -> Any:
    import json

    try:
        return json.loads(value)
    except Exception:
        return value


def _load(session: Session, filing_id: str) -> Filing:
    filing = session.get(Filing, filing_id)
    if filing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="filing not found")
    return filing


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(
    return_: PITReturn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = create_filing(session=session, return_=return_)
    return _filing_to_dict(filing)


@router.get("/{filing_id}")
async def read(
    filing_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    return _filing_to_dict(_load(session, filing_id))


@router.put("/{filing_id}")
async def update(
    filing_id: str,
    return_: PITReturn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    update_filing_return(session=session, filing=filing, return_=return_)
    return _filing_to_dict(filing)


@router.post("/{filing_id}/audit")
async def run_audit(
    filing_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    report = audit_filing(session=session, filing=filing)
    return {"filing": _filing_to_dict(filing), "audit": report.to_dict()}


@router.post("/{filing_id}/pack")
@limiter.limit("10/minute")
async def build_pack(
    request: Request,
    filing_id: str,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
) -> dict[str, Any]:
    filing = _load(session, filing_id)
    try:
        pack = generate_pack(session=session, storage=storage, filing=filing)
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


class SubmitRequest(BaseModel):
    language: str = "en"
    # When true, enqueue the submission to a Celery worker instead of
    # running it inline on the request thread. Falls back to inline if
    # CELERY_ENABLED is false, so the flag is always safe to pass.
    async_: bool = False


@router.post("/{filing_id}/submit")
async def submit_to_nrs(
    filing_id: str,
    body: SubmitRequest | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Submit a finalized filing to NRS.

    If NRS credentials are not configured (e.g. local dev, Railway preview
    without a real sandbox), the service runs a deterministic simulated
    submission and marks the outcome with `simulated=true`. The UI should
    render that status distinctly from a real `accepted`.

    When `async_=true` AND `CELERY_ENABLED=true` AND a worker is
    running, the filing is enqueued and the endpoint returns
    `{queued: true, task_id: ...}`. Otherwise the submission runs inline
    (existing behaviour) and returns `{submission: {...}}`.
    """
    body = body or SubmitRequest()
    filing = _load(session, filing_id)

    # Opportunistic async path — only when the flag AND infra are set up.
    from app.celery_app import is_async_enabled

    if body.async_ and is_async_enabled():
        from app.tasks.filing_tasks import submit_filing_to_nrs_task

        result = submit_filing_to_nrs_task.delay(
            filing_id=filing.id, language=body.language
        )
        return {
            "filing": _filing_to_dict(filing),
            "queued": True,
            "task_id": result.id,
        }

    try:
        outcome = submit_filing_to_nrs(
            session=session, filing=filing, language=body.language
        )
    except SubmissionConfigError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return {"filing": _filing_to_dict(filing), "submission": outcome.to_dict()}


@router.get("/{filing_id}/pack.json")
async def download_json(
    filing_id: str,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
) -> Response:
    filing = _load(session, filing_id)
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
