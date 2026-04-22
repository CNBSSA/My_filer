"""PDF renderer smoke test (P4.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.filing.pdf import render_pack_pdf
from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity
from app.filing.serialize import build_canonical_pack


def _example_return() -> PITReturn:
    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
            residential_address="1 Ikoyi Crescent, Lagos",
            email="chidi@example.com",
        ),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
        ],
        declaration=True,
    )


def test_render_pack_pdf_emits_pdf_bytes() -> None:
    pack = build_canonical_pack(_example_return())
    pdf = render_pack_pdf(pack)
    assert isinstance(pdf, bytes)
    # PDF magic number.
    assert pdf.startswith(b"%PDF")
    # Non-trivial size — our renderer packs several tables + paragraphs.
    assert len(pdf) > 2000
