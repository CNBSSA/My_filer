"""UBL 3.0 envelope schemas.

We model the envelope as an ordered dict of *section -> field-map*.
This keeps the envelope structure decoupled from the specific 55 field
names in `app.tax.statutory.ubl_fields`, which are still placeholders.

When NRS publishes the field list:

  1. Replace `UBL_REQUIRED_FIELDS_2026` in `statutory/ubl_fields.py`.
  2. Typed wrappers for each section (e.g. `InvoiceHeader`, `SellerParty`)
     can then be added here — the validator keeps working either way.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UBLSection(BaseModel):
    """One of the 8 top-level sections. Keys inside `fields` are the NRS
    UBL paths; values may be strings, numbers, booleans, or nested dicts /
    lists (the latter for `invoice_lines` + `tax_breakdown`)."""

    name: str
    fields: dict[str, Any] = Field(default_factory=dict)


class UBLEnvelope(BaseModel):
    """Envelope the NRS MBS gateway expects for every e-invoice / return.

    A well-formed envelope always contains the 8 documented sections; the
    field count inside each section must match the current statutory
    table. `validate_envelope` enforces both invariants.
    """

    version: str = "ubl-3.0"
    profile: str = Field(
        default="urn:mai-filer:ubl-3.0:mbs-einvoice-v1",
        description="UBL customization + profile URI; NRS-specific.",
    )
    sections: list[UBLSection] = Field(default_factory=list)

    def section(self, name: str) -> UBLSection | None:
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def all_fields_flat(self) -> dict[str, Any]:
        """Flatten `<section>.<field>` pairs into one dict for reporting."""
        flat: dict[str, Any] = {}
        for section in self.sections:
            for key, value in section.fields.items():
                flat[f"{section.name}.{key}"] = value
        return flat
