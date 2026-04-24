"""Document service — upload, persist, extract.

v1 does extraction **synchronously** inside the upload endpoint. Phase 6 /
Celery moves this to a background worker; the service API stays the same.

Privacy note (per COMPLIANCE.md §1): we persist the extracted structured
data for convenience, but the raw bytes stay only in object storage keyed
by `storage_key`. Nothing PII-bearing is logged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Document
from app.documents.extractor import VisionExtractor
from app.documents.schemas import DocumentKind
from app.documents.storage import StorageAdapter

log = logging.getLogger("mai_filer.documents")

# Kinds that Mai auto-extracts on upload. Other kinds (e.g., cac_certificate)
# are stored but not yet extracted; `read_document_extraction` returns null
# until a later phase wires up a schema.

# Magic byte signatures for content types we accept.
_MAGIC_BYTES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),          # WebP starts RIFF...WEBP
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
]


def _detect_content_type(data: bytes) -> str | None:
    """Return detected MIME type from magic bytes, or None if unrecognised."""
    for magic, mime in _MAGIC_BYTES:
        if data[:len(magic)] == magic:
            return mime
    return None


EXTRACTABLE_KINDS: frozenset[DocumentKind] = frozenset({"payslip", "bank_statement", "receipt"})


# Content types Claude Vision accepts that we allow for uploads.
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
    }
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class UnsupportedContentTypeError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


def upload_and_extract(
    *,
    session: Session,
    storage: StorageAdapter,
    extractor: VisionExtractor,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    kind: DocumentKind,
    user_id: str | None = None,
    thread_id: str | None = None,
    run_extraction: bool = True,
) -> Document:
    """Persist the upload + (optionally) run Vision extraction synchronously.

    Returns the committed `Document` row; the caller is responsible for
    refreshing / serializing it.
    """
    # Re-validate content type against file magic bytes to prevent spoofing.
    detected = _detect_content_type(file_bytes)
    if detected and detected not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedContentTypeError(
            f"file magic bytes indicate {detected!r}, which is not allowed."
        )
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedContentTypeError(
            f"unsupported content type: {content_type}. "
            f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}"
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError(
            f"upload is {len(file_bytes)} bytes; limit is {MAX_UPLOAD_BYTES}"
        )

    blob = storage.put(file_bytes, content_type=content_type, filename=filename)

    document = Document(
        user_id=user_id,
        thread_id=thread_id,
        filename=filename,
        content_type=content_type,
        size_bytes=blob.size_bytes,
        storage_key=blob.key,
        kind=kind,
    )
    session.add(document)
    session.flush()

    if run_extraction and kind in EXTRACTABLE_KINDS:
        try:
            if kind == "payslip":
                extraction, _ = extractor.extract_payslip(
                    file_bytes=file_bytes,
                    content_type=content_type,
                    filename=filename,
                )
            elif kind == "bank_statement":
                extraction, _ = extractor.extract_bank_statement(
                    file_bytes=file_bytes,
                    content_type=content_type,
                    filename=filename,
                )
            else:  # "receipt"
                extraction, _ = extractor.extract_receipt(
                    file_bytes=file_bytes,
                    content_type=content_type,
                    filename=filename,
                )
            document.extraction_json = extraction.model_dump(mode="json")
            document.extracted_at = datetime.now(timezone.utc)
        except Exception as exc:  # surface; Mai can see the error and ask user to retry
            log.warning("%s extraction failed: %s", kind, exc)
            document.extraction_error = str(exc)

    session.commit()
    session.refresh(document)
    return document
