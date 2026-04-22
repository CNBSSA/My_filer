"""Pydantic schemas for documents (upload metadata, extractions, records).

Only **payslip** is wired end-to-end in this commit (P3.4). Receipt, bank
statement, and CAC certificate schemas follow in P3.6 / P3.7.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

DocumentKind = Literal["payslip", "receipt", "bank_statement", "cac_certificate", "unknown"]


class LineItem(BaseModel):
    """A single labelled line on a payslip (e.g. a bonus or a deduction)."""

    label: str
    amount: Decimal
    category: Literal["earning", "deduction"] = "earning"


class PayslipExtraction(BaseModel):
    """Structured output from a payslip extraction.

    Currency is assumed to be Nigerian naira (₦); all amounts are gross of VAT
    where applicable. Dates use ISO-8601.
    """

    employer_name: str | None = None
    employee_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    pay_frequency: Literal["monthly", "biweekly", "weekly", "annual", "unknown"] = "monthly"

    gross_income: Decimal
    paye_withheld: Decimal = Field(default=Decimal("0"))
    pension_contribution: Decimal = Field(default=Decimal("0"))
    nhis_contribution: Decimal = Field(default=Decimal("0"))
    cra_amount: Decimal | None = None
    net_pay: Decimal | None = None

    other_earnings: list[LineItem] = Field(default_factory=list)
    other_deductions: list[LineItem] = Field(default_factory=list)

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None

    def annualized_gross(self) -> Decimal:
        """Project the extracted period's gross income onto an annual figure."""
        frequency_multipliers: dict[str, int] = {
            "monthly": 12,
            "biweekly": 26,
            "weekly": 52,
            "annual": 1,
            "unknown": 1,
        }
        multiplier = frequency_multipliers.get(self.pay_frequency, 1)
        return self.gross_income * Decimal(multiplier)


class DocumentRecord(BaseModel):
    """API response shape for a stored document."""

    id: str
    kind: DocumentKind
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    extraction: dict[str, Any] | None = None
    extraction_error: str | None = None
