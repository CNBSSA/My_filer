"""UBL 3.0 — 55 mandatory fields across 8 sections — 2026 **PLACEHOLDER**.

Per `docs/KNOWLEDGE_BASE.md §8`, every MBS e-invoice / filing payload
must carry exactly 55 mandatory data fields arranged into 8 sections.
The owner has not yet supplied the authoritative field list, so this
module defines the **section scaffolding** and an illustrative field
enumeration that sums to 55. The field names below mirror common UBL
3.0 usage but are NOT guaranteed to match NRS's binding list.

When the owner supplies the 55-field list:

  1. Replace every `"TODO_..."` entry in `UBL_REQUIRED_FIELDS_2026` with
     the canonical UBL 3.0 path (e.g. `cbc:IssueDate`, `cac:AccountingSupplierParty`).
  2. Keep the 55-field invariant intact (the validator asserts this).
  3. Change `UBL_SOURCE` away from `"PLACEHOLDER:..."`.

`apps/api/app/filing/ubl/validate.py` asserts the invariants (count=55,
sections=8) on every envelope generated.
"""

from __future__ import annotations

# The 8 locked sections. NRS documentation calls them out but the
# *precise field names* inside each section are the missing piece.
UBL_SECTIONS: tuple[str, ...] = (
    "invoice_header",
    "seller_party",
    "buyer_party",
    "tax_period",
    "invoice_lines",
    "tax_breakdown",
    "monetary_totals",
    "cryptographic_stamp",
)


# --- PLACEHOLDER VALUES ---------------------------------------------------
# Field counts per section sum to 55. Names are illustrative only.
UBL_REQUIRED_FIELDS_2026: dict[str, list[str]] = {
    "invoice_header": [
        "TODO_invoice_id",
        "TODO_issue_date",
        "TODO_issue_time",
        "TODO_invoice_type_code",
        "TODO_currency_code",
        "TODO_document_reference",
    ],
    "seller_party": [
        "TODO_seller_cac_rc",
        "TODO_seller_nin_or_tin",
        "TODO_seller_legal_name",
        "TODO_seller_trade_name",
        "TODO_seller_vat_status",
        "TODO_seller_address",
        "TODO_seller_contact",
    ],
    "buyer_party": [
        "TODO_buyer_cac_rc",
        "TODO_buyer_nin_or_tin",
        "TODO_buyer_legal_name",
        "TODO_buyer_address",
        "TODO_buyer_contact",
        "TODO_buyer_is_registered_for_vat",
    ],
    "tax_period": [
        "TODO_period_start",
        "TODO_period_end",
        "TODO_reporting_period_code",
    ],
    "invoice_lines": [
        "TODO_line_id",
        "TODO_line_item_description",
        "TODO_line_quantity",
        "TODO_line_unit_price",
        "TODO_line_net_amount",
        "TODO_line_tax_category",
        "TODO_line_tax_rate",
        "TODO_line_tax_amount",
        "TODO_line_discount_amount",
        "TODO_line_allowance_reason_code",
        "TODO_line_uom_code",
        "TODO_line_reference",
    ],
    "tax_breakdown": [
        "TODO_taxable_amount_vat",
        "TODO_tax_amount_vat",
        "TODO_taxable_amount_wht",
        "TODO_tax_amount_wht",
        "TODO_zero_rated_amount",
        "TODO_exempt_amount",
        "TODO_tax_exemption_reason_code",
    ],
    "monetary_totals": [
        "TODO_line_extension_total",
        "TODO_tax_exclusive_total",
        "TODO_tax_inclusive_total",
        "TODO_prepaid_amount",
        "TODO_payable_amount",
        "TODO_rounding_amount",
        "TODO_allowance_total",
        "TODO_charge_total",
    ],
    "cryptographic_stamp": [
        "TODO_irn",
        "TODO_csid",
        "TODO_qr_payload",
        "TODO_signed_hash",
        "TODO_signing_time",
        "TODO_previous_irn_hash",
    ],
}


UBL_SOURCE: str = (
    "PLACEHOLDER: illustrative 55-field structure; awaiting NRS-published "
    "UBL 3.0 field list per ADR-0002 / ROADMAP Phase 9"
)


def total_required_fields() -> int:
    return sum(len(v) for v in UBL_REQUIRED_FIELDS_2026.values())
