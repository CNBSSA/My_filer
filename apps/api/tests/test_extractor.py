"""Vision extractor tests (P3.5) — mocked VisionClient."""

from __future__ import annotations

import pytest

from app.documents.extractor import (
    ExtractionRaw,
    ExtractionUsage,
    PAYSLIP_TOOL_NAME,
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
