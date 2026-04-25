"""PDF pack renderer (P4.3) — reportlab.

Produces a one-to-three-page branded PDF suitable for:
  * NRS self-service portal manual upload.
  * Walk-in submission at an NRS office.
  * User's own record-keeping.

The PDF is rendered directly from the canonical JSON pack (see
`serialize.build_canonical_pack`) so it never drifts from the JSON we
persist.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

STYLES = getSampleStyleSheet()
H1 = ParagraphStyle(
    "MaiH1",
    parent=STYLES["Heading1"],
    fontSize=18,
    leading=22,
    spaceAfter=6,
    textColor=colors.HexColor("#0b5345"),
)
H2 = ParagraphStyle(
    "MaiH2",
    parent=STYLES["Heading2"],
    fontSize=13,
    leading=16,
    spaceBefore=12,
    spaceAfter=4,
    textColor=colors.HexColor("#1a5276"),
)
META = ParagraphStyle(
    "MaiMeta",
    parent=STYLES["Normal"],
    fontSize=9,
    leading=12,
    textColor=colors.grey,
)
BODY = ParagraphStyle(
    "MaiBody",
    parent=STYLES["Normal"],
    fontSize=10,
    leading=14,
)
BANNER_TEXT = ParagraphStyle(
    "MaiBanner",
    parent=STYLES["Normal"],
    fontSize=9,
    leading=13,
    textColor=colors.HexColor("#7d6608"),
)


def _submission_banner() -> Table:
    """Amber-tinted banner indicating this is a manual-submission copy.

    Placed at the top of every PDF so no reader — including NRS staff or
    a CA reviewing the return — mistakes it for a filed (NRS-accepted) return.
    """
    # A4 content width: 210mm - 18mm left - 18mm right = 174mm
    text = (
        "<b>MANUAL SUBMISSION COPY</b><br/>"
        "This return has been prepared for submission to the Nigeria Revenue Service (NRS). "
        "Upload this document to the NRS Self-Service Portal (Rev360) to obtain your "
        "Invoice Reference Number (IRN) and Cryptographic Stamp Identifier (CSID). "
        "This document does <b>not</b> constitute a filed return until it is accepted by NRS "
        "and an IRN is issued."
    )
    table = Table([[Paragraph(text, BANNER_TEXT)]], colWidths=[174 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef9e7")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d4ac0d")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _naira(amount: str) -> str:
    """Render a string naira figure ('690000.00') with thousands separators."""
    try:
        as_float = float(amount)
    except (ValueError, TypeError):
        return f"₦{amount}"
    return f"₦{as_float:,.2f}"


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(rows, colWidths=[60 * mm, 110 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _grid(rows: list[list[str]], header: list[str], widths_mm: list[int]) -> Table:
    data = [header, *rows]
    table = Table(data, colWidths=[w * mm for w in widths_mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b5345")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f7")]),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def render_pack_pdf(pack: dict[str, Any]) -> bytes:
    """Return the PDF bytes for a canonical JSON pack."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Mai Filer — PIT/PAYE {pack.get('tax_year')}",
        author="Mai Filer",
    )
    story: list[Any] = []

    # --- Header --------------------------------------------------------
    story.append(Paragraph("Mai Filer — Personal Income Tax Return", H1))
    story.append(
        Paragraph(
            f"Tax year {pack['tax_year']} · Pack version {pack.get('pack_version', '—')} · "
            f"Generated {pack.get('generated_at', '')}",
            META,
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(_submission_banner())
    story.append(Spacer(1, 4 * mm))

    # --- Taxpayer ------------------------------------------------------
    tp = pack["taxpayer"]
    story.append(Paragraph("Taxpayer", H2))
    story.append(
        _kv_table(
            [
                ("Full name", tp.get("full_name") or "—"),
                ("NIN", tp.get("nin") or "—"),
                ("Date of birth", tp.get("date_of_birth") or "—"),
                ("Marital status", tp.get("marital_status") or "—"),
                ("Address", tp.get("residential_address") or "—"),
                ("Phone", tp.get("phone") or "—"),
                ("Email", tp.get("email") or "—"),
            ]
        )
    )

    # --- Income sources -----------------------------------------------
    story.append(Paragraph("Income sources", H2))
    sources = pack.get("income", {}).get("sources", [])
    if sources:
        rows = [
            [
                s.get("payer_name", "—"),
                s.get("kind", "—"),
                f"{s.get('period_start', '')} → {s.get('period_end', '')}",
                _naira(s.get("gross_amount", "0")),
                _naira(s.get("tax_withheld", "0")),
            ]
            for s in sources
        ]
        story.append(
            _grid(
                rows,
                header=["Payer", "Kind", "Period", "Gross", "Tax withheld"],
                widths_mm=[45, 25, 40, 30, 30],
            )
        )
    else:
        story.append(Paragraph("(no income sources recorded)", BODY))

    total_gross = pack.get("income", {}).get("total_gross", "0")
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Total gross income: {_naira(total_gross)}", BODY))

    # --- Deductions ---------------------------------------------------
    story.append(Paragraph("Deductions & reliefs", H2))
    ded = pack["deductions"]
    story.append(
        _kv_table(
            [
                ("Pension", _naira(ded.get("pension", "0"))),
                ("NHIS", _naira(ded.get("nhis", "0"))),
                ("CRA", _naira(ded.get("cra", "0"))),
                ("Life insurance", _naira(ded.get("life_insurance", "0"))),
                ("NHF", _naira(ded.get("nhf", "0"))),
                *[
                    (f"Other — {item['label']}", _naira(item["amount"]))
                    for item in ded.get("other_reliefs", [])
                ],
                ("Total deductions", _naira(ded.get("total", "0"))),
            ]
        )
    )

    # --- PIT computation ----------------------------------------------
    story.append(Paragraph("PIT computation (2026 bands)", H2))
    comp = pack["computation"]
    band_rows = [
        [
            str(b["order"]),
            b["name"],
            f"{float(b['rate']) * 100:.2f}%",
            _naira(b["taxable_amount"]),
            _naira(b["tax_amount"]),
        ]
        for b in comp["bands"]
    ]
    story.append(
        _grid(
            band_rows,
            header=["#", "Band", "Rate", "Taxable in band", "Tax"],
            widths_mm=[10, 55, 20, 45, 40],
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        _kv_table(
            [
                ("Chargeable income", _naira(comp.get("chargeable_income", "0"))),
                ("Total tax", _naira(comp.get("total_tax", "0"))),
                ("Effective rate", f"{float(comp.get('effective_rate', '0')) * 100:.2f}%"),
            ]
        )
    )

    # --- Settlement ---------------------------------------------------
    story.append(Paragraph("Settlement", H2))
    settle = pack.get("settlement", {})
    story.append(
        _kv_table(
            [
                ("PAYE already withheld", _naira(settle.get("paye_already_withheld", "0"))),
                ("Net payable / (refund)", _naira(settle.get("net_payable", "0"))),
                ("Direction", settle.get("direction", "—")),
            ]
        )
    )

    # --- Declaration --------------------------------------------------
    story.append(Paragraph("Declaration", H2))
    decl = pack.get("declaration", {})
    story.append(Paragraph(decl.get("statement", ""), BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Affirmed: <b>{'Yes' if decl.get('affirmed') else 'No'}</b>",
            BODY,
        )
    )

    # --- Footer -------------------------------------------------------
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "This pack was generated by Mai Filer. To file, upload this document to the "
            "NRS Self-Service Portal (Rev360) at self-service.nrs.gov.ng. "
            "This return is not filed until NRS issues an Invoice Reference Number (IRN). "
            "Generated by Mai Filer — myfiler.ng.",
            META,
        )
    )

    doc.build(story)
    return buffer.getvalue()
