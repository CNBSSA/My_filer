"""Documents router — upload, retrieve, list (P3.1c)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.session import get_session
from app.documents.extractor import VisionExtractor, get_default_vision_extractor
from app.documents.schemas import DocumentKind, DocumentRecord
from app.documents.service import (
    UnsupportedContentTypeError,
    UploadTooLargeError,
    upload_and_extract,
)
from app.documents.storage import StorageAdapter, get_default_storage

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def get_storage() -> StorageAdapter:
    return get_default_storage()


def get_extractor() -> VisionExtractor:
    return get_default_vision_extractor()


def _to_record(doc: Document) -> DocumentRecord:
    return DocumentRecord(
        id=doc.id,
        kind=doc.kind,  # type: ignore[arg-type]
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
        extraction=doc.extraction_json,
        extraction_error=doc.extraction_error,
    )


@router.post("", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File()],
    kind: Annotated[DocumentKind, Form()] = "payslip",
    thread_id: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_session),
    storage: StorageAdapter = Depends(get_storage),
    extractor: VisionExtractor = Depends(get_extractor),
) -> DocumentRecord:
    """Accept a payslip (v1) and extract it synchronously.

    Supported kinds in v1: `payslip`. Other kinds are accepted and stored
    but not auto-extracted until P3.6 / P3.7.
    """
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empty upload"
        )
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload"

    try:
        document = upload_and_extract(
            session=session,
            storage=storage,
            extractor=extractor,
            file_bytes=data,
            filename=filename,
            content_type=content_type,
            kind=kind,
            thread_id=thread_id,
        )
    except UnsupportedContentTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc

    return _to_record(document)


@router.get("/{document_id}", response_model=DocumentRecord)
async def get_document(
    document_id: str,
    session: Session = Depends(get_session),
) -> DocumentRecord:
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    return _to_record(doc)


@router.get("", response_model=list[DocumentRecord])
async def list_documents(
    session: Session = Depends(get_session),
    limit: int = 20,
) -> list[DocumentRecord]:
    """Recent documents, newest first. No auth yet — the caller sees everything."""
    rows = (
        session.query(Document)
        .order_by(Document.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [_to_record(doc) for doc in rows]
