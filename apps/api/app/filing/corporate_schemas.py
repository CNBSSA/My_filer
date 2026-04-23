"""Corporate (CIT) return schemas (Phase 9).

Parallel to `PITReturn` (individual) and `NGOReturn` (exempt bodies): a
corporate CIT return bundles the taxpayer, turnover + expense blocks,
the CIT computation, and the declaration into one validated Pydantic
payload.

Identity key: **CAC Part-A RC** (Limited / PLC / BN). The P9.6 CAC
verification flow feeds this schema — the RC number here should already
have been cross-checked against `cac_records`.

Like the NGO surface, this schema can be parsed + serialized + audited
*today* against the placeholder `CIT_BANDS_2026`. The service that
computes liability gates on `assert_confirmed(CIT_SOURCE)` before it
will produce a downloadable pack in production.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

CompanyType = Literal["LTD", "PLC", "BN", "LLP", "OTHER"]

ExpenseKind = Literal[
    "cost_of_sales",
    "salaries_wages",
    "rent",
    "utilities",
    "depreciation",
    "professional_fees",
    "marketing",
    "interest",
    "other",
]


class CorporateTaxpayer(BaseModel):
    """CAC Part-A registered taxpayer."""

    rc_number: str = Field(min_length=1, max_length=64)
    company_name: str = Field(min_length=2, max_length=255)
    company_type: CompanyType = "LTD"
    tin: str | None = Field(default=None, max_length=32)
    registered_address: str | None = None
    industry: str | None = Field(default=None, max_length=120)
    email: str | None = None
    phone: str | None = None
    primary_officer_name: str | None = Field(default=None, max_length=200)
    primary_officer_nin: str | None = Field(
        default=None, max_length=11, pattern=r"^\d{11}$"
    )


class RevenueLine(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(ge=Decimal("0"))


class ExpenseLine(BaseModel):
    kind: ExpenseKind = "other"
    label: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(ge=Decimal("0"))


class CITBandLine(BaseModel):
    tier: str
    rate: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal


class CITComputation(BaseModel):
    annual_turnover: Decimal
    total_expenses: Decimal
    assessable_profit: Decimal
    tier: str
    cit_rate: Decimal
    cit_amount: Decimal
    tertiary_rate: Decimal
    tertiary_amount: Decimal
    total_payable: Decimal
    bands: list[CITBandLine] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CITReturn(BaseModel):
    """A complete CIT return for one corporate taxpayer, one tax year."""

    tax_year: int = Field(ge=2025, le=2100)
    period_start: date
    period_end: date

    taxpayer: CorporateTaxpayer

    revenues: list[RevenueLine] = Field(default_factory=list)
    expenses: list[ExpenseLine] = Field(default_factory=list)

    declared_turnover: Decimal | None = Field(default=None, ge=Decimal("0"))
    declared_assessable_profit: Decimal | None = Field(
        default=None,
        description=(
            "Optional explicit assessable profit. If absent, the serializer "
            "uses (sum of revenues - sum of expenses)."
        ),
    )

    wht_already_suffered: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    advance_tax_paid: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    computation: CITComputation | None = None

    supporting_document_ids: list[str] = Field(default_factory=list)

    declaration: bool = Field(
        default=False,
        description=(
            "Must be True before the pack is finalized. Authorised officer "
            "affirms the return is true and complete."
        ),
    )

    notes: str | None = None

    # Populated by the serializer for convenience.
    total_revenue: Decimal | None = None
    total_expenses: Decimal | None = None
    net_payable: Decimal | None = None
