"""Audit Shield (P4.5 / P4.6) — pre-submission validator.

Catches what NRS would catch, before NRS sees it. Produces a three-state
status (`green` / `yellow` / `red`) with a list of findings. Mai Filer
refuses to offer a download until the status is at least `green`.

Severity → status mapping:
  * any `error` finding   → red
  * no errors, any `warn` → yellow
  * no errors, no warns   → green

Checks implemented (v1 — individual PIT / PAYE):

  1. NIN must be 11 digits (schema already enforces this; double-check).
  2. Full name must be non-empty and plausible (>= 2 chars).
  3. Tax year must be current or prior (no future filings).
  4. Declaration must be affirmed.
  5. At least one income source.
  6. Each income source's tax_withheld <= gross_amount.
  7. Pension contribution must not exceed 50% of gross (warning heuristic).
  8. Total deductions must not exceed gross income (error).
  9. Declared paye_already_withheld must equal sum(source.tax_withheld)
     within kobo precision (warning if mismatched).
 10. Recomputed total_tax must match `computation.total_tax` (error if not).
 11. Every supporting_document_id referenced in income_sources must also
     appear in the return's `supporting_document_ids` list (warning).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.filing.schemas import PITReturn
from app.filing.serialize import compute_return_totals

Severity = Literal["info", "warn", "error"]
AuditStatus = Literal["green", "yellow", "red"]


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: Severity
    message: str
    field_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "field_path": self.field_path,
        }


@dataclass
class AuditReport:
    status: AuditStatus
    findings: list[AuditFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
        }


KOBO_TOLERANCE = Decimal("0.01")


def _status_from_findings(findings: list[AuditFinding]) -> AuditStatus:
    if any(f.severity == "error" for f in findings):
        return "red"
    if any(f.severity == "warn" for f in findings):
        return "yellow"
    return "green"


def audit(return_: PITReturn, *, today: date | None = None) -> AuditReport:
    """Run every v1 check. `today` is injectable for deterministic tests."""
    findings: list[AuditFinding] = []
    today = today or date.today()

    # 1 & 2. Identity sanity — schema enforces NIN regex + min len on name,
    # but we re-check in case a raw dict bypassed validation upstream.
    if not return_.taxpayer.nin or not return_.taxpayer.nin.isdigit() or len(return_.taxpayer.nin) != 11:
        findings.append(
            AuditFinding(
                "IDENTITY_NIN_INVALID",
                "error",
                "NIN must be exactly 11 digits.",
                "taxpayer.nin",
            )
        )
    if not return_.taxpayer.full_name or len(return_.taxpayer.full_name.strip()) < 2:
        findings.append(
            AuditFinding(
                "IDENTITY_NAME_MISSING",
                "error",
                "Taxpayer full name is required.",
                "taxpayer.full_name",
            )
        )

    # 3. Future tax year.
    if return_.tax_year > today.year:
        findings.append(
            AuditFinding(
                "TAX_YEAR_IN_FUTURE",
                "error",
                f"Tax year {return_.tax_year} is in the future.",
                "tax_year",
            )
        )

    # 4. Declaration affirmed.
    if not return_.declaration:
        findings.append(
            AuditFinding(
                "DECLARATION_NOT_AFFIRMED",
                "error",
                "Taxpayer declaration has not been affirmed.",
                "declaration",
            )
        )

    # 5. At least one income source.
    if not return_.income_sources:
        findings.append(
            AuditFinding(
                "NO_INCOME_SOURCES",
                "error",
                "Return has no income sources.",
                "income_sources",
            )
        )

    # 6. Per-source sanity.
    for idx, src in enumerate(return_.income_sources):
        if src.tax_withheld > src.gross_amount:
            findings.append(
                AuditFinding(
                    "INCOME_WITHHELD_EXCEEDS_GROSS",
                    "error",
                    (
                        f"Income source #{idx+1} ({src.payer_name}) has tax_withheld "
                        f"greater than gross_amount."
                    ),
                    f"income_sources[{idx}].tax_withheld",
                )
            )

    # 7. Pension heuristic.
    gross_total = sum((s.gross_amount for s in return_.income_sources), Decimal("0"))
    if gross_total > 0 and return_.deductions.pension > gross_total / 2:
        findings.append(
            AuditFinding(
                "PENSION_EXCEEDS_HALF_GROSS",
                "warn",
                (
                    "Pension contribution exceeds 50% of gross income — this is "
                    "unusually high. Confirm the amount before filing."
                ),
                "deductions.pension",
            )
        )

    # 8. Deductions > gross.
    total_deductions = return_.deductions.total()
    if total_deductions > gross_total:
        findings.append(
            AuditFinding(
                "DEDUCTIONS_EXCEED_GROSS",
                "error",
                "Total deductions exceed gross income.",
                "deductions",
            )
        )

    # 9. Withheld consistency.
    sum_source_withheld = sum(
        (s.tax_withheld for s in return_.income_sources), Decimal("0")
    )
    if return_.paye_already_withheld and abs(
        return_.paye_already_withheld - sum_source_withheld
    ) > KOBO_TOLERANCE:
        findings.append(
            AuditFinding(
                "WITHHELD_MISMATCH",
                "warn",
                (
                    f"Declared paye_already_withheld ({return_.paye_already_withheld}) "
                    f"differs from the sum of per-source tax_withheld "
                    f"({sum_source_withheld})."
                ),
                "paye_already_withheld",
            )
        )

    # 10. Recomputed total_tax vs declared computation.
    authoritative = compute_return_totals(return_)
    if authoritative.computation is not None and return_.computation is not None:
        delta = abs(authoritative.computation.total_tax - return_.computation.total_tax)
        if delta > KOBO_TOLERANCE:
            findings.append(
                AuditFinding(
                    "COMPUTATION_MISMATCH",
                    "error",
                    (
                        f"Declared total_tax ({return_.computation.total_tax}) differs "
                        f"from the recomputed figure ({authoritative.computation.total_tax}) "
                        f"by more than one kobo."
                    ),
                    "computation.total_tax",
                )
            )

    # 11. Cross-reference supporting documents.
    referenced = {
        s.supporting_document_id
        for s in return_.income_sources
        if s.supporting_document_id
    }
    for ref in referenced:
        if ref not in return_.supporting_document_ids:
            findings.append(
                AuditFinding(
                    "SUPPORTING_DOC_NOT_ATTACHED",
                    "warn",
                    (
                        f"Income source references document {ref} but it is not in "
                        f"supporting_document_ids."
                    ),
                    "supporting_document_ids",
                )
            )

    return AuditReport(status=_status_from_findings(findings), findings=findings)
