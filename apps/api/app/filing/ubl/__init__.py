"""UBL 3.0 envelope package (Phase 9 scaffolding).

Structure mirrors the eight sections NRS documents; the *field names*
inside each section come from `app.tax.statutory.ubl_fields` so a
confirmed 55-field list swaps in without code changes.

Exports:
  * UBLEnvelope  — the Pydantic model describing an e-invoice / return.
  * serialize_json / serialize_xml — canonical bytes.
  * validate_envelope — asserts count=55, sections=8, required fields present.
  * UBLValidationError — raised on a structural violation.
"""

from __future__ import annotations

from app.filing.ubl.schemas import UBLEnvelope, UBLSection
from app.filing.ubl.serialize import serialize_json, serialize_xml
from app.filing.ubl.validate import UBLValidationError, validate_envelope

__all__ = [
    "UBLEnvelope",
    "UBLSection",
    "UBLValidationError",
    "serialize_json",
    "serialize_xml",
    "validate_envelope",
]
