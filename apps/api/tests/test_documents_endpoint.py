"""Document upload/retrieval endpoint tests (P3.5)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.documents import get_extractor, get_storage
from app.documents.extractor import (
    ExtractionUsage,
    VisionExtractor,
)
from app.documents.schemas import PayslipExtraction
from app.documents.storage import InMemoryStorage
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


class FakeExtractor(VisionExtractor):
    """VisionExtractor that returns a preset extraction, no Claude involved."""

    def __init__(
        self, extraction: PayslipExtraction | Exception | None = None
    ) -> None:
        self._extraction = extraction
        self.calls: list[dict] = []

    def extract_payslip(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ):
        self.calls.append(
            {"size": len(file_bytes), "content_type": content_type, "filename": filename}
        )
        if isinstance(self._extraction, Exception):
            raise self._extraction
        assert self._extraction is not None
        return self._extraction, ExtractionUsage(input_tokens=100, output_tokens=50)


def _happy_extraction() -> PayslipExtraction:
    return PayslipExtraction(
        employer_name="Globacom Ltd",
        employee_name="Chidi Okafor",
        pay_frequency="monthly",
        gross_income=Decimal("420000"),
        paye_withheld=Decimal("31000"),
        pension_contribution=Decimal("33600"),
        nhis_contribution=Decimal("5000"),
        cra_amount=Decimal("100000"),
        net_pay=Decimal("350400"),
        confidence=0.92,
    )


def _override(extractor: VisionExtractor, storage: InMemoryStorage | None = None):
    storage = storage or InMemoryStorage()
    app.dependency_overrides[get_extractor] = lambda: extractor
    app.dependency_overrides[get_storage] = lambda: storage
    return storage


def test_upload_payslip_returns_extraction(db_session) -> None:
    extractor = FakeExtractor(_happy_extraction())
    storage = _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("march.png", b"\x89PNG\r\n\x1a\nabc", "image/png")},
            data={"kind": "payslip"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["kind"] == "payslip"
        assert body["filename"] == "march.png"
        assert body["extraction"]["employer_name"] == "Globacom Ltd"
        assert body["extraction"]["gross_income"] == "420000"
        assert body["extraction_error"] is None
        # Blob landed in storage.
        assert len(storage._blobs) == 1  # type: ignore[attr-defined]
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_unsupported_content_type() -> None:
    extractor = FakeExtractor(_happy_extraction())
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={
                "file": ("notes.txt", b"not a payslip", "text/plain"),
            },
            data={"kind": "payslip"},
        )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


def test_upload_rejects_empty_file() -> None:
    extractor = FakeExtractor(_happy_extraction())
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("empty.png", b"", "image/png")},
            data={"kind": "payslip"},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_upload_surfaces_extraction_error_without_failing_upload() -> None:
    extractor = FakeExtractor(RuntimeError("vision unavailable"))
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("march.png", b"\x89PNG...", "image/png")},
            data={"kind": "payslip"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["extraction"] is None
        assert "vision unavailable" in body["extraction_error"]
    finally:
        app.dependency_overrides.clear()


def test_non_payslip_kinds_are_stored_without_extraction() -> None:
    extractor = FakeExtractor(_happy_extraction())
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("receipt.jpg", b"\xff\xd8\xff...", "image/jpeg")},
            data={"kind": "receipt"},
        )
        assert response.status_code == 201
        body = response.json()
        # Receipt extraction lands in P3.6; for now it's stored untouched.
        assert body["extraction"] is None
        assert extractor.calls == []
    finally:
        app.dependency_overrides.clear()


def test_get_and_list_documents() -> None:
    extractor = FakeExtractor(_happy_extraction())
    _override(extractor)
    try:
        client = TestClient(app)
        upload = client.post(
            "/v1/documents",
            files={"file": ("march.png", b"\x89PNG...", "image/png")},
            data={"kind": "payslip"},
        )
        doc_id = upload.json()["id"]

        single = client.get(f"/v1/documents/{doc_id}")
        assert single.status_code == 200
        assert single.json()["id"] == doc_id

        missing = client.get("/v1/documents/does-not-exist")
        assert missing.status_code == 404

        listing = client.get("/v1/documents")
        assert listing.status_code == 200
        assert len(listing.json()) == 1
    finally:
        app.dependency_overrides.clear()
