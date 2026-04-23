"""NGO annual return schemas (Phase 11).

Distinct from `PITReturn` / future `CITReturn` because an NGO return is
primarily an **accountability** document — it proves the organization
still qualifies for exemption and accounts for WHT it remitted on
payments it made, rather than computing a tax liability.

Identity key: **CAC Part-C RC** (Incorporated Trustees). Individuals
use NIN; commercial entities use CAC Part-A RC; NGOs use Part-C.

The purpose enum is backed by `app.tax.statutory.ngo_rules.NGO_EXEMPT_PURPOSES`
so when the owner supplies the confirmed list, Pydantic acceptance
updates with the data — no code change.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.tax.statutory.ngo_rules import NGO_EXEMPT_PURPOSES

ExemptPurpose = Literal[
    "charitable",
    "educational",
    "religious",
    "scientific",
    "cultural",
    "social_welfare",
    "other",
]

WhtRecipientCategory = Literal[
    "individual",
    "corporate",
    "partnership",
    "foreign_entity",
    "other",
]


class Organization(BaseModel):
    """Registered exempt body. CAC Part-C is the primary identifier."""

    cac_part_c_rc: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: str | None = None
    exemption_reference: str | None = Field(default=None, max_length=128)
    purpose: ExemptPurpose = "other"
    registered_address: str | None = None
    email: str | None = None
    phone: str | None = None


class NGOIncomeBlock(BaseModel):
    local_donations: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    foreign_donations: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    government_grants: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    foundation_grants: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    program_income: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    investment_income: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    other_income: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    def total(self) -> Decimal:
        return (
            self.local_donations
            + self.foreign_donations
            + self.government_grants
            + self.foundation_grants
            + self.program_income
            + self.investment_income
            + self.other_income
        )


class NGOExpenditureBlock(BaseModel):
    program_expenses: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    administrative: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    fundraising: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    other: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    def total(self) -> Decimal:
        return (
            self.program_expenses
            + self.administrative
            + self.fundraising
            + self.other
        )


class WHTScheduleRow(BaseModel):
    """One row in the WHT-remitted schedule: NGO withheld X on payment Y."""

    period_month: int = Field(ge=1, le=12)
    transaction_class: str = Field(min_length=1, max_length=64)
    recipient_category: WhtRecipientCategory = "other"
    gross_amount: Decimal = Field(ge=Decimal("0"))
    wht_amount: Decimal = Field(ge=Decimal("0"))
    recipient_reference: str | None = Field(default=None, max_length=128)
    remittance_receipt: str | None = Field(default=None, max_length=128)


class NGOReturn(BaseModel):
    """An NGO annual return for one exempt body, one tax year."""

    tax_year: int = Field(ge=2025, le=2100)
    period_start: date
    period_end: date

    organization: Organization

    income: NGOIncomeBlock = Field(default_factory=NGOIncomeBlock)
    expenditure: NGOExpenditureBlock = Field(default_factory=NGOExpenditureBlock)

    wht_schedule: list[WHTScheduleRow] = Field(default_factory=list)

    exemption_status_declaration: bool = Field(
        default=False,
        description=(
            "Trustees affirm the organisation continues to meet the "
            "exemption criteria for this tax year."
        ),
    )

    supporting_document_ids: list[str] = Field(default_factory=list)

    declaration: bool = Field(
        default=False,
        description=(
            "Authorised signatory affirms the return is true and complete."
        ),
    )

    notes: str | None = None

    # Recomputed aggregates populated by the serializer.
    total_income: Decimal | None = None
    total_expenditure: Decimal | None = None
    total_wht_remitted: Decimal | None = None
    net_result: Decimal | None = None  # income - expenditure


def known_exempt_purposes() -> tuple[str, ...]:
    return NGO_EXEMPT_PURPOSES
