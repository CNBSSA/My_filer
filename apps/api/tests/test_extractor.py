"""Vision extractor tests (P3.5) — mocked VisionClient."""

from __future__ import annotations

import pytest

from app.documents.extractor import (
    BANK_STATEMENT_TOOL_NAME,
    ExtractionRaw,
    ExtractionUsage,
    PAYSLIP_TOOL_NAME,
    RECEIPT_TOOL_NAME,
    VisionExtractor,
)


class FakeVisionClient:
    def __init__(self, tool_input: dict, record: dict | None = None) -> None:
        self.tool_input = tool_input
        self.record = record if record is not None else {}
        self.calls: list[dict] = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return ExtractionRaw(
            tool_input=self.tool_input,
            usage=ExtractionUsage(input_tokens=300, output_tokens=80),
        )


def test_extract_payslip_happy_path() -> None:
    fake = FakeVisionClient(
        tool_input={
            "employer_name": "Globacom Ltd",
            "employee_name": "Chidi Okafor",
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "pay_frequency": "monthly",
            "gross_income": 420_000,
            "paye_withheld": 31_000,
            "pension_contribution": 33_600,
            "nhis_contribution": 5_000,
            "cra_amount": 100_000,
            "net_pay": 350_400,
            "other_earnings": [],
            "other_deductions": [],
            "confidence": 0.92,
            "notes": None,
        }
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    extraction, usage = extractor.extract_payslip(
        file_bytes=b"\x89PNG\r\n\x1a\n...fake bytes...",
        content_type="image/png",
        filename="march.png",
    )
    assert str(extraction.gross_income) == "420000"
    assert str(extraction.pension_contribution) == "33600"
    assert extraction.pay_frequency == "monthly"
    assert extraction.confidence == pytest.approx(0.92)
    # Annualized gross projects monthly x12.
    assert str(extraction.annualized_gross()) == "5040000"
    assert usage.output_tokens == 80
    # Client saw the payslip tool + the base64-encoded bytes.
    call = fake.calls[0]
    assert call["tool"]["name"] == PAYSLIP_TOOL_NAME
    assert call["content_type"] == "image/png"
    assert call["data_b64"]  # not empty


def test_extract_payslip_validates_missing_required_field() -> None:
    fake = FakeVisionClient(tool_input={"pay_frequency": "monthly"})  # no gross_income
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    with pytest.raises(Exception):  # pydantic ValidationError subclass
        extractor.extract_payslip(
            file_bytes=b"x", content_type="image/png", filename="x.png"
        )


def test_extract_payslip_forwards_pdf_content_type() -> None:
    fake = FakeVisionClient(
        tool_input={"gross_income": 100_000, "pay_frequency": "monthly"}
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    extractor.extract_payslip(
        file_bytes=b"%PDF-1.4 ...", content_type="application/pdf"
    )
    assert fake.calls[0]["content_type"] == "application/pdf"


# ---------------------------------------------------------------------------
# Bank statement (P3.6)
# ---------------------------------------------------------------------------


def test_extract_bank_statement_happy_path() -> None:
    fake = FakeVisionClient(
        tool_input={
            "bank_name": "GTBank",
            "account_holder_name": "Chidi Okafor",
            "account_number_last4": "3456",
            "statement_period_start": "2026-03-01",
            "statement_period_end": "2026-03-31",
            "currency": "NGN",
            "opening_balance": 120_000,
            "closing_balance": 430_000,
            "total_credits": 500_000,
            "total_debits": 190_000,
            "transactions": [
                {
                    "date": "2026-03-05",
                    "description": "GLOBACOM SALARY MARCH",
                    "direction": "credit",
                    "amount": 420_000,
                    "balance_after": 540_000,
                    "category": "salary",
                },
                {
                    "date": "2026-03-12",
                    "description": "PENCOM MONTHLY CONTRIBUTION",
                    "direction": "debit",
                    "amount": 33_600,
                    "balance_after": 506_400,
                    "category": "pension_contribution",
                },
            ],
            "confidence": 0.88,
            "notes": None,
        }
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    extraction, _ = extractor.extract_bank_statement(
        file_bytes=b"%PDF-1.4 ...", content_type="application/pdf"
    )
    assert extraction.bank_name == "GTBank"
    assert extraction.account_number_last4 == "3456"
    assert len(extraction.transactions) == 2
    salary = extraction.transactions[0]
    assert salary.direction == "credit"
    assert salary.category == "salary"
    assert fake.calls[0]["tool"]["name"] == BANK_STATEMENT_TOOL_NAME


def test_extract_bank_statement_validates_required_totals() -> None:
    fake = FakeVisionClient(tool_input={})  # missing total_credits + total_debits
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    with pytest.raises(Exception):
        extractor.extract_bank_statement(
            file_bytes=b"x", content_type="application/pdf"
        )


def test_extract_bank_statement_rejects_bad_direction_enum() -> None:
    fake = FakeVisionClient(
        tool_input={
            "total_credits": 0,
            "total_debits": 0,
            "transactions": [
                {
                    "description": "mystery",
                    "direction": "neither",  # invalid per schema
                    "amount": 100,
                }
            ],
        }
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    with pytest.raises(Exception):
        extractor.extract_bank_statement(
            file_bytes=b"x", content_type="application/pdf"
        )


# ---------------------------------------------------------------------------
# Receipt (P3.7)
# ---------------------------------------------------------------------------


def test_extract_receipt_happy_path() -> None:
    fake = FakeVisionClient(
        tool_input={
            "vendor_name": "AXA Mansard Insurance",
            "vendor_tin": "12345-0001",
            "receipt_number": "INS-2026-01-0042",
            "issue_date": "2026-02-14",
            "currency": "NGN",
            "subtotal": 180_000,
            "vat_amount": 0,
            "total_amount": 180_000,
            "receipt_type": "insurance",
            "items": [
                {"description": "Life cover — Q1 2026", "quantity": 1, "total": 180_000}
            ],
            "likely_tax_deductible": True,
            "confidence": 0.95,
            "notes": None,
        }
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    extraction, _ = extractor.extract_receipt(
        file_bytes=b"\x89PNG ...", content_type="image/png"
    )
    assert extraction.vendor_name == "AXA Mansard Insurance"
    assert extraction.receipt_type == "insurance"
    assert extraction.likely_tax_deductible is True
    assert len(extraction.items) == 1
    assert fake.calls[0]["tool"]["name"] == RECEIPT_TOOL_NAME


def test_extract_receipt_requires_total_amount() -> None:
    fake = FakeVisionClient(
        tool_input={"vendor_name": "Sterling Bank", "receipt_type": "service"}
    )
    extractor = VisionExtractor(client=fake, model="claude-sonnet-4-6")
    with pytest.raises(Exception):
        extractor.extract_receipt(file_bytes=b"x", content_type="image/png")
