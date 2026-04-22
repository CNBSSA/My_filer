"""UBL 3.0 envelope validator.

Invariants checked:

  1. Envelope declares exactly 8 sections, in the order defined by
     `UBL_SECTIONS`.
  2. The flattened field count is exactly 55 (matches the current
     statutory table).
  3. Every required field listed in `UBL_REQUIRED_FIELDS_2026` exists
     on its section. Values may be `None` — that's reported as a
     *missing value*, not a structural error.
  4. No unknown fields appear inside a section (unknown = not in the
     required list for that section).

Output is a structured report so the caller — Audit Shield, Mai, or a
CI check — can surface exactly what went wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.filing.ubl.schemas import UBLEnvelope
from app.tax.statutory.ubl_fields import (
    UBL_REQUIRED_FIELDS_2026,
    UBL_SECTIONS,
    total_required_fields,
)

Severity = Literal["error", "warn", "info"]


class UBLValidationError(ValueError):
    """Raised for unrecoverable structural violations (section count / order)."""


@dataclass(frozen=True)
class UBLFinding:
    code: str
    severity: Severity
    message: str
    path: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class UBLReport:
    ok: bool
    field_count: int
    section_count: int
    findings: list[UBLFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "field_count": self.field_count,
            "section_count": self.section_count,
            "findings": [f.to_dict() for f in self.findings],
        }


def validate_envelope(envelope: UBLEnvelope) -> UBLReport:
    findings: list[UBLFinding] = []

    # Invariant 1: 8 sections in canonical order.
    if len(envelope.sections) != len(UBL_SECTIONS):
        findings.append(
            UBLFinding(
                code="UBL-SECTION-COUNT",
                severity="error",
                message=(
                    f"envelope has {len(envelope.sections)} sections, "
                    f"expected {len(UBL_SECTIONS)}"
                ),
            )
        )
    else:
        for idx, (actual, expected) in enumerate(
            zip(envelope.sections, UBL_SECTIONS)
        ):
            if actual.name != expected:
                findings.append(
                    UBLFinding(
                        code="UBL-SECTION-ORDER",
                        severity="error",
                        message=(
                            f"section #{idx+1} is '{actual.name}', expected '{expected}'"
                        ),
                        path=f"sections[{idx}]",
                    )
                )

    total_fields = 0
    for section in envelope.sections:
        required = UBL_REQUIRED_FIELDS_2026.get(section.name, [])
        required_set = set(required)
        provided_set = set(section.fields.keys())

        # Missing fields — always a structural error.
        for missing in sorted(required_set - provided_set):
            findings.append(
                UBLFinding(
                    code="UBL-FIELD-MISSING",
                    severity="error",
                    message=f"section '{section.name}' missing required field '{missing}'",
                    path=f"{section.name}.{missing}",
                )
            )

        # Unknown fields — warning, not fatal (forward-compat).
        for unknown in sorted(provided_set - required_set):
            findings.append(
                UBLFinding(
                    code="UBL-FIELD-UNKNOWN",
                    severity="warn",
                    message=f"section '{section.name}' carries unknown field '{unknown}'",
                    path=f"{section.name}.{unknown}",
                )
            )

        # Null values — informational; Audit Shield can decide whether
        # to escalate per field.
        for name, value in section.fields.items():
            if name in required_set and value is None:
                findings.append(
                    UBLFinding(
                        code="UBL-FIELD-NULL",
                        severity="info",
                        message=f"required field '{name}' is null in '{section.name}'",
                        path=f"{section.name}.{name}",
                    )
                )

        total_fields += len(provided_set & required_set)

    expected_total = total_required_fields()
    if total_fields != expected_total:
        findings.append(
            UBLFinding(
                code="UBL-FIELD-COUNT",
                severity="error",
                message=(
                    f"envelope covers {total_fields} required fields, "
                    f"expected {expected_total}"
                ),
            )
        )

    ok = not any(f.severity == "error" for f in findings)
    return UBLReport(
        ok=ok,
        field_count=total_fields,
        section_count=len(envelope.sections),
        findings=findings,
    )
