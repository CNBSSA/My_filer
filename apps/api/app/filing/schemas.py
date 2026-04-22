"""Filing return schemas — v1 individual (PIT / PAYE).

These schemas describe what Mai Filer bundles into a downloadable pack for
a Nigerian individual taxpayer. They are deliberately minimal but complete:
enough for NRS manual submission via the self-service portal, auditable by
the Audit Shield, and round-trippable through Pydantic.

SME / UBL 3.0 + 55-field payloads are v2 (Phase 9) and live in a different
schema file when they land.

Money is always `Decimal`, dates are `date`, tax year is `int`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

IncomeSourceKind = Literal[
    "employment",
    "self_employment",
    "rental",
    "investment",
    "pension_income",
    "other",
]

MaritalStatus = Literal["single", "married", "divorced", "widowed", "unknown"]


class LineItem(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    amount: Decimal


class TaxpayerIdentity(BaseModel):
    """Minimal identity block. Full name is required by NRS; other fields are
    optional so we don't block a user who hasn't captured them yet."""

    nin: str = Field(
        min_length=11,
        max_length=11,
        pattern=r"^\d{11}$",
        description="11-digit National Identification Number.",
    )
    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date | None = None
    marital_status: MaritalStatus = "unknown"
    residential_address: str | None = None
    phone: str | None = None
    email: str | None = None


class IncomeSource(BaseModel):
    kind: IncomeSourceKind
    payer_name: str = Field(min_length=1, max_length=200)
    gross_amount: Decimal = Field(ge=Decimal("0"))
    tax_withheld: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    period_start: date
    period_end: date
    supporting_document_id: str | None = None


class Deductions(BaseModel):
    pension: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    nhis: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    cra: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    life_insurance: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    nhf: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    other_reliefs: list[LineItem] = Field(default_factory=list)

    def total(self) -> Decimal:
        other = sum((item.amount for item in self.other_reliefs), Decimal("0"))
        return (
            self.pension
            + self.nhis
            + self.cra
            + self.life_insurance
            + self.nhf
            + other
        )


class PITBandLine(BaseModel):
    order: int
    name: str
    rate: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal


class PITComputation(BaseModel):
    annual_income: Decimal
    total_deductions: Decimal
    chargeable_income: Decimal
    bands: list[PITBandLine]
    total_tax: Decimal
    effective_rate: Decimal


class PITReturn(BaseModel):
    """A complete PIT / PAYE return for one taxpayer, one tax year."""

    tax_year: int = Field(ge=2025, le=2100)
    period_start: date
    period_end: date

    taxpayer: TaxpayerIdentity

    income_sources: list[IncomeSource] = Field(default_factory=list)
    deductions: Deductions = Field(default_factory=Deductions)
    computation: PITComputation | None = None

    paye_already_withheld: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    supporting_document_ids: list[str] = Field(default_factory=list)

    declaration: bool = Field(
        default=False,
        description=(
            "Must be True before the pack is finalized. By setting this flag "
            "the taxpayer affirms the return is true and complete."
        ),
    )

    notes: str | None = None

    # Aggregates — filled in by the serializer for convenience. Authoritative
    # values live inside `computation` + `income_sources`.
    total_gross_income: Decimal | None = None
    net_payable: Decimal | None = None
