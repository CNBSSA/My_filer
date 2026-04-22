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


class BankTransaction(BaseModel):
    """One line on a bank statement."""

    model_config = {"populate_by_name": True}

    transaction_date: date | None = Field(default=None, alias="date")
    description: str
    direction: Literal["credit", "debit"]
    amount: Decimal
    balance_after: Decimal | None = None
    category: Literal[
        "salary",
        "business_income",
        "rent_received",
        "pension_contribution",
        "nhis_contribution",
        "nhf_contribution",
        "tax_payment",
        "transfer",
        "fee",
        "utility",
        "other",
    ] = "other"


class BankStatementExtraction(BaseModel):
    """Structured output from a Nigerian bank statement.

    We deliberately do **not** capture full account numbers — only the last
    four digits — to minimize PII leaking into prompts and logs (NDPR
    minimization per COMPLIANCE.md §1). The account holder's full name is
    also optional; the caller cross-references it with the taxpayer identity
    before using any figure in a return.
    """

    bank_name: str | None = None
    account_holder_name: str | None = None
    account_number_last4: str | None = Field(default=None, max_length=4)
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    currency: str = "NGN"

    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    # Totals are required — an extraction that cannot produce them is not
    # safe to trust, so we surface it as an error rather than defaulting
    # to zero (which would look like a clean zero-activity statement).
    total_credits: Decimal
    total_debits: Decimal

    transactions: list[BankTransaction] = Field(default_factory=list)

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None


class ReceiptItem(BaseModel):
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal


class ReceiptExtraction(BaseModel):
    """Structured output from a receipt or invoice image.

    Useful for: business-expense substantiation, input VAT credits for
    SMEs (v2), and documentation of life insurance, NHIS, NHF, or medical
    payments that support individual reliefs.
    """

    vendor_name: str | None = None
    vendor_tin: str | None = None
    receipt_number: str | None = None
    issue_date: date | None = None

    currency: str = "NGN"
    subtotal: Decimal | None = None
    vat_amount: Decimal | None = None
    total_amount: Decimal

    receipt_type: Literal[
        "purchase",
        "service",
        "utility",
        "rent",
        "insurance",
        "medical",
        "donation",
        "tax_payment",
        "other",
    ] = "other"

    items: list[ReceiptItem] = Field(default_factory=list)

    likely_tax_deductible: bool | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None


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
