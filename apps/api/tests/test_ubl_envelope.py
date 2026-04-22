"""UBL 3.0 envelope tests (P9.3)."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from app.filing.ubl import UBLEnvelope, UBLSection, serialize_json, serialize_xml, validate_envelope
from app.tax.statutory.ubl_fields import UBL_REQUIRED_FIELDS_2026, UBL_SECTIONS, total_required_fields


def _full_envelope() -> UBLEnvelope:
    """Build a complete envelope by filling every required field with a
    non-null placeholder value."""
    sections = []
    for name in UBL_SECTIONS:
        fields = {f: f"{name}:{f}" for f in UBL_REQUIRED_FIELDS_2026[name]}
        sections.append(UBLSection(name=name, fields=fields))
    return UBLEnvelope(sections=sections)


def test_full_envelope_validates_ok() -> None:
    report = validate_envelope(_full_envelope())
    assert report.ok is True
    assert report.section_count == 8
    assert report.field_count == 55
    assert report.field_count == total_required_fields()
    # No errors, possibly info-level findings only.
    for finding in report.findings:
        assert finding.severity != "error"


def test_missing_field_is_a_structural_error() -> None:
    envelope = _full_envelope()
    section = envelope.sections[0]  # invoice_header
    first_field = next(iter(section.fields))
    del section.fields[first_field]
    report = validate_envelope(envelope)
    assert report.ok is False
    codes = {f.code for f in report.findings}
    assert "UBL-FIELD-MISSING" in codes
    assert "UBL-FIELD-COUNT" in codes


def test_null_value_is_info_not_error() -> None:
    envelope = _full_envelope()
    envelope.sections[0].fields[next(iter(envelope.sections[0].fields))] = None
    report = validate_envelope(envelope)
    # Null value stays ok at the structural level.
    assert report.ok is True
    codes = {f.code for f in report.findings}
    assert "UBL-FIELD-NULL" in codes


def test_unknown_field_warning() -> None:
    envelope = _full_envelope()
    envelope.sections[0].fields["extra_field_not_in_spec"] = "surprise"
    report = validate_envelope(envelope)
    # Still ok (warning, not error), but flagged.
    assert report.ok is True
    codes = {f.code for f in report.findings}
    assert "UBL-FIELD-UNKNOWN" in codes


def test_wrong_section_count_fails() -> None:
    envelope = _full_envelope()
    envelope.sections = envelope.sections[:-1]
    report = validate_envelope(envelope)
    assert report.ok is False
    codes = {f.code for f in report.findings}
    assert "UBL-SECTION-COUNT" in codes


def test_wrong_section_order_fails() -> None:
    envelope = _full_envelope()
    envelope.sections[0], envelope.sections[1] = envelope.sections[1], envelope.sections[0]
    report = validate_envelope(envelope)
    assert report.ok is False
    codes = {f.code for f in report.findings}
    assert "UBL-SECTION-ORDER" in codes


def test_serialize_json_roundtrip() -> None:
    envelope = _full_envelope()
    blob = serialize_json(envelope)
    assert isinstance(blob, bytes)
    parsed = json.loads(blob)
    assert parsed["version"] == "ubl-3.0"
    assert [s["name"] for s in parsed["sections"]] == list(UBL_SECTIONS)


def test_serialize_xml_emits_expected_root() -> None:
    envelope = _full_envelope()
    blob = serialize_xml(envelope)
    assert blob.startswith(b"<?xml")
    root = ET.fromstring(blob)
    assert root.tag == "UBLEnvelope"
    assert root.attrib["version"] == "ubl-3.0"
    # 8 <Section> children.
    section_names = [el.get("name") for el in root.findall("Section")]
    assert section_names == list(UBL_SECTIONS)
