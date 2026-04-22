"""UBL 3.0 envelope serializers (JSON + XML).

JSON is produced via `json.dumps` with stable ordering. XML uses stdlib
`xml.etree.ElementTree` — no lxml dependency — which keeps production
install light. Fidelity is sufficient for the MBS preview path; when
NRS publishes a schema we tighten to xsd-verified serialization with
signed canonicalisation.
"""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from app.filing.ubl.schemas import UBLEnvelope


def serialize_json(envelope: UBLEnvelope, *, indent: int | None = 2) -> bytes:
    """Canonical JSON. Sections preserve their declared order."""
    return json.dumps(
        envelope.model_dump(mode="json"),
        ensure_ascii=False,
        indent=indent,
        sort_keys=False,
    ).encode("utf-8")


def _append_value(parent: ET.Element, name: str, value: object) -> None:
    el = ET.SubElement(parent, name)
    if value is None:
        el.set("nil", "true")
    elif isinstance(value, (list, tuple)):
        for item in value:
            _append_value(el, "item", item)
    elif isinstance(value, dict):
        for k, v in value.items():
            _append_value(el, k, v)
    else:
        el.text = str(value)


def serialize_xml(envelope: UBLEnvelope) -> bytes:
    """Minimal XML representation. Namespace placeholders stand in for the
    actual UBL namespaces until NRS confirms the schema."""
    root = ET.Element(
        "UBLEnvelope",
        attrib={
            "version": envelope.version,
            "profile": envelope.profile,
        },
    )
    for section in envelope.sections:
        section_el = ET.SubElement(root, "Section", attrib={"name": section.name})
        for name, value in section.fields.items():
            _append_value(section_el, name, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
