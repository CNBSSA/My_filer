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
from app.documents.schemas import (
    BankStatementExtraction,
    BankTransaction,
    PayslipExtraction,
    ReceiptExtraction,
    ReceiptItem,
)
from app.documents.storage import InMemoryStorage
from app.main import app

pytestmark = pytest.mark.usefixtures("override_db")


class FakeExtractor(VisionExtractor):
    """VisionExtractor that returns a preset extraction per kind; no Claude."""

    def __init__(
        self,
        payslip: PayslipExtraction | Exception | None = None,
        bank_statement: BankStatementExtraction | Exception | None = None,
        receipt: ReceiptExtraction | Exception | None = None,
    ) -> None:
        self._payslip = payslip
        self._bank_statement = bank_statement
        self._receipt = receipt
        self.calls: list[dict] = []

    def _record(self, kind: str, file_bytes: bytes, content_type: str, filename):
        self.calls.append(
            {
                "kind": kind,
                "size": len(file_bytes),
                "content_type": content_type,
                "filename": filename,
            }
        )

    def extract_payslip(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ):
        self._record("payslip", file_bytes, content_type, filename)
        if isinstance(self._payslip, Exception):
            raise self._payslip
        assert self._payslip is not None, "no payslip extraction configured"
        return self._payslip, ExtractionUsage(input_tokens=100, output_tokens=50)

    def extract_bank_statement(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ):
        self._record("bank_statement", file_bytes, content_type, filename)
        if isinstance(self._bank_statement, Exception):
            raise self._bank_statement
        assert self._bank_statement is not None, "no bank_statement extraction configured"
        return self._bank_statement, ExtractionUsage(input_tokens=200, output_tokens=120)

    def extract_receipt(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ):
        self._record("receipt", file_bytes, content_type, filename)
        if isinstance(self._receipt, Exception):
            raise self._receipt
        assert self._receipt is not None, "no receipt extraction configured"
        return self._receipt, ExtractionUsage(input_tokens=80, output_tokens=40)


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


def _happy_bank_statement() -> BankStatementExtraction:
    return BankStatementExtraction(
        bank_name="GTBank",
        account_holder_name="Chidi Okafor",
        account_number_last4="3456",
        total_credits=Decimal("500000"),
        total_debits=Decimal("190000"),
        transactions=[
            BankTransaction(
                description="GLOBACOM SALARY MARCH",
                direction="credit",
                amount=Decimal("420000"),
                category="salary",
            )
        ],
        confidence=0.88,
    )


def _happy_receipt() -> ReceiptExtraction:
    return ReceiptExtraction(
        vendor_name="AXA Mansard",
        total_amount=Decimal("180000"),
        receipt_type="insurance",
        items=[ReceiptItem(description="Life cover Q1", total=Decimal("180000"))],
        likely_tax_deductible=True,
        confidence=0.95,
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


def test_upload_bank_statement_returns_extraction() -> None:
    """P3.6 — bank statement upload runs the dedicated extractor."""
    extractor = FakeExtractor(bank_statement=_happy_bank_statement())
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={
                "file": ("march-statement.pdf", b"%PDF-1.4 ...", "application/pdf")
            },
            data={"kind": "bank_statement"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["kind"] == "bank_statement"
        assert body["extraction"]["bank_name"] == "GTBank"
        assert body["extraction"]["account_number_last4"] == "3456"
        assert body["extraction"]["transactions"][0]["category"] == "salary"
        assert extractor.calls[0]["kind"] == "bank_statement"
    finally:
        app.dependency_overrides.clear()


def test_upload_receipt_returns_extraction() -> None:
    """P3.7 — receipt upload runs the receipt extractor."""
    extractor = FakeExtractor(receipt=_happy_receipt())
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("insurance.jpg", b"\xff\xd8\xff...", "image/jpeg")},
            data={"kind": "receipt"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["kind"] == "receipt"
        assert body["extraction"]["vendor_name"] == "AXA Mansard"
        assert body["extraction"]["receipt_type"] == "insurance"
        assert body["extraction"]["likely_tax_deductible"] is True
        assert extractor.calls[0]["kind"] == "receipt"
    finally:
        app.dependency_overrides.clear()


def test_unknown_kind_is_stored_without_extraction() -> None:
    """Kinds outside EXTRACTABLE_KINDS are persisted but not auto-extracted."""
    extractor = FakeExtractor(_happy_extraction())  # payslip slot, not called
    _override(extractor)
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/documents",
            files={"file": ("cac.pdf", b"%PDF-1.4 ...", "application/pdf")},
            data={"kind": "cac_certificate"},
        )
        assert response.status_code == 201
        body = response.json()
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
