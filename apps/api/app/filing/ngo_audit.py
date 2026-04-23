"""NGO Audit Shield (P11.4).

Same shape as the PIT Audit Shield (`filing/audit.py`) — structured
`AuditFinding` list with severity-derived `AuditStatus`. The checks
are NGO-specific:

  1. CAC Part-C RC matches the statutory pattern.
  2. Organization legal name is non-empty.
  3. Tax year is not in the future.
  4. Organization purpose is in the exempt list (warn only — reform
     may enumerate new purposes).
  5. Income + expenditure are consistent (no negative totals).
  6. WHT schedule rows: wht_amount <= gross_amount each.
  7. Aggregate `total_wht_remitted` matches the schedule sum.
  8. Exemption-status declaration affirmed.
  9. Authorised-signatory declaration affirmed.
 10. At least one income or expenditure entry (a fully-empty return
     is almost certainly an error).
 11. Supporting-document IDs are non-empty when program expenses > 0
     (warning — programme evidence is usually required).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.filing.ngo_schemas import NGOReturn
from app.filing.ngo_serialize import compute_return_totals
from app.tax.statutory.ngo_rules import (
    NGO_CAC_PART_C_PATTERN,
    NGO_EXEMPT_PURPOSES,
)

Severity = Literal["info", "warn", "error"]
AuditStatus = Literal["green", "yellow", "red"]

KOBO_TOLERANCE = Decimal("0.01")

_CAC_RE = re.compile(NGO_CAC_PART_C_PATTERN)


@dataclass(frozen=True)
class NGOAuditFinding:
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
class NGOAuditReport:
    status: AuditStatus
    findings: list[NGOAuditFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
        }


def _status_from_findings(findings: list[NGOAuditFinding]) -> AuditStatus:
    if any(f.severity == "error" for f in findings):
        return "red"
    if any(f.severity == "warn" for f in findings):
        return "yellow"
    return "green"


def audit(return_: NGOReturn, *, today: date | None = None) -> NGOAuditReport:
    """Run every Phase 11 check. `today` is injectable for deterministic tests."""
    findings: list[NGOAuditFinding] = []
    today = today or date.today()
    org = return_.organization

    # 1. CAC Part-C pattern.
    if not org.cac_part_c_rc or not _CAC_RE.match(org.cac_part_c_rc):
        findings.append(
            NGOAuditFinding(
                "NGO_IDENTITY_CAC_INVALID",
                "error",
                (
                    f"CAC Part-C RC '{org.cac_part_c_rc}' does not match the "
                    f"expected pattern ({NGO_CAC_PART_C_PATTERN})."
                ),
                "organization.cac_part_c_rc",
            )
        )

    # 2. Legal name.
    if not org.legal_name or len(org.legal_name.strip()) < 2:
        findings.append(
            NGOAuditFinding(
                "NGO_IDENTITY_NAME_MISSING",
                "error",
                "Organization legal name is required.",
                "organization.legal_name",
            )
        )

    # 3. Future tax year.
    if return_.tax_year > today.year:
        findings.append(
            NGOAuditFinding(
                "NGO_TAX_YEAR_IN_FUTURE",
                "error",
                f"Tax year {return_.tax_year} is in the future.",
                "tax_year",
            )
        )

    # 4. Exempt-purpose sanity.
    if org.purpose not in NGO_EXEMPT_PURPOSES and org.purpose != "other":
        findings.append(
            NGOAuditFinding(
                "NGO_PURPOSE_UNRECOGNIZED",
                "warn",
                (
                    f"Purpose '{org.purpose}' is not on the current exempt list. "
                    f"Verify whether NRS recognises this category."
                ),
                "organization.purpose",
            )
        )
    if org.purpose == "other":
        findings.append(
            NGOAuditFinding(
                "NGO_PURPOSE_OTHER",
                "warn",
                (
                    "Purpose is declared as 'other'. NRS will probably require a "
                    "free-text description — attach it before filing."
                ),
                "organization.purpose",
            )
        )

    # 5. Income + expenditure totals are derived; the schema rejects
    # negatives at parse time, so this just guards dict injection paths.
    if return_.income.total() < 0 or return_.expenditure.total() < 0:
        findings.append(
            NGOAuditFinding(
                "NGO_TOTALS_NEGATIVE",
                "error",
                "Income or expenditure total is negative.",
                "income/expenditure",
            )
        )

    # 6 + 7. WHT schedule sanity.
    declared_wht_total = Decimal("0")
    for idx, row in enumerate(return_.wht_schedule):
        if row.wht_amount > row.gross_amount:
            findings.append(
                NGOAuditFinding(
                    "NGO_WHT_EXCEEDS_GROSS",
                    "error",
                    (
                        f"WHT schedule row {idx + 1}: wht_amount greater than "
                        f"gross_amount."
                    ),
                    f"wht_schedule[{idx}].wht_amount",
                )
            )
        declared_wht_total += row.wht_amount

    authoritative = compute_return_totals(return_)
    if authoritative.total_wht_remitted is not None:
        delta = abs(authoritative.total_wht_remitted - declared_wht_total)
        if delta > KOBO_TOLERANCE:
            findings.append(
                NGOAuditFinding(
                    "NGO_WHT_SCHEDULE_MISMATCH",
                    "error",
                    (
                        f"Aggregate WHT ({authoritative.total_wht_remitted}) "
                        f"does not equal the sum of the schedule rows "
                        f"({declared_wht_total})."
                    ),
                    "wht_schedule",
                )
            )

    # 8. Exemption status declaration.
    if not return_.exemption_status_declaration:
        findings.append(
            NGOAuditFinding(
                "NGO_EXEMPTION_NOT_AFFIRMED",
                "error",
                "Trustees have not affirmed continued exemption status.",
                "exemption_status_declaration",
            )
        )

    # 9. General declaration.
    if not return_.declaration:
        findings.append(
            NGOAuditFinding(
                "NGO_DECLARATION_NOT_AFFIRMED",
                "error",
                "Authorised signatory declaration has not been affirmed.",
                "declaration",
            )
        )

    # 10. Empty return.
    income_total = return_.income.total()
    expenditure_total = return_.expenditure.total()
    if income_total == 0 and expenditure_total == 0 and not return_.wht_schedule:
        findings.append(
            NGOAuditFinding(
                "NGO_EMPTY_RETURN",
                "error",
                "Return has no income, no expenditure, and no WHT rows.",
                None,
            )
        )

    # 11. Programme evidence expectation.
    if (
        return_.expenditure.program_expenses > 0
        and not return_.supporting_document_ids
    ):
        findings.append(
            NGOAuditFinding(
                "NGO_SUPPORTING_DOCS_MISSING",
                "warn",
                (
                    "Programme expenses are declared but no supporting "
                    "documents are attached."
                ),
                "supporting_document_ids",
            )
        )

    return NGOAuditReport(status=_status_from_findings(findings), findings=findings)
