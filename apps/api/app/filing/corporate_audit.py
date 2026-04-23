"""Corporate (CIT) Audit Shield (Phase 9).

Same structure as `filing/audit.py` (PIT) and `filing/ngo_audit.py` (NGO):
structured `CorporateAuditFinding` list → severity-derived `AuditStatus`.

Checks:

  1. CAC RC number is present + alphanumeric.
  2. Company legal name is present.
  3. Tax year is not in the future.
  4. At least one revenue line OR a declared_turnover.
  5. Revenue + expense rows are non-negative (schema-level, but guard
     dict injection paths).
  6. Turnover is internally consistent: if both declared_turnover AND
     revenue rows are present, their sum cannot exceed the declared
     turnover by more than a kobo (we permit rounding).
  7. Assessable profit is not wildly negative (warn > 50% of turnover).
  8. Declaration has been affirmed.
  9. At least one supporting document when net payable > 0 (warning).
 10. CIT statutory source still marked PLACEHOLDER — always emits a
     warning so the caller knows the liability figure is illustrative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.filing.corporate_schemas import CITReturn
from app.filing.corporate_serialize import compute_return_totals
from app.tax.statutory.cit_bands import CIT_SOURCE

Severity = Literal["info", "warn", "error"]
AuditStatus = Literal["green", "yellow", "red"]

KOBO_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class CorporateAuditFinding:
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
class CorporateAuditReport:
    status: AuditStatus
    findings: list[CorporateAuditFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
        }


def _status_from_findings(findings: list[CorporateAuditFinding]) -> AuditStatus:
    if any(f.severity == "error" for f in findings):
        return "red"
    if any(f.severity == "warn" for f in findings):
        return "yellow"
    return "green"


def audit(return_: CITReturn, *, today: date | None = None) -> CorporateAuditReport:
    findings: list[CorporateAuditFinding] = []
    today = today or date.today()
    tp = return_.taxpayer

    # 1. RC number.
    cleaned = (tp.rc_number or "").strip()
    if not cleaned or not cleaned.replace("-", "").replace("/", "").isalnum():
        findings.append(
            CorporateAuditFinding(
                "CIT_IDENTITY_RC_INVALID",
                "error",
                f"RC number '{tp.rc_number}' is missing or not alphanumeric.",
                "taxpayer.rc_number",
            )
        )

    # 2. Company name.
    if not tp.company_name or len(tp.company_name.strip()) < 2:
        findings.append(
            CorporateAuditFinding(
                "CIT_IDENTITY_NAME_MISSING",
                "error",
                "Company legal name is required.",
                "taxpayer.company_name",
            )
        )

    # 3. Future tax year.
    if return_.tax_year > today.year:
        findings.append(
            CorporateAuditFinding(
                "CIT_TAX_YEAR_IN_FUTURE",
                "error",
                f"Tax year {return_.tax_year} is in the future.",
                "tax_year",
            )
        )

    # 4. Revenue or declared turnover.
    if not return_.revenues and return_.declared_turnover is None:
        findings.append(
            CorporateAuditFinding(
                "CIT_NO_REVENUE",
                "error",
                "At least one revenue line or a declared_turnover is required.",
                "revenues",
            )
        )

    # 5. Negative aggregates guard.
    neg_rev = any(r.amount < 0 for r in return_.revenues)
    neg_exp = any(e.amount < 0 for e in return_.expenses)
    if neg_rev or neg_exp:
        findings.append(
            CorporateAuditFinding(
                "CIT_NEGATIVE_LINE",
                "error",
                "Revenue or expense line is negative.",
                "revenues/expenses",
            )
        )

    # 6. Turnover consistency.
    authoritative = compute_return_totals(return_)
    if (
        return_.declared_turnover is not None
        and return_.revenues
        and (authoritative.total_revenue or Decimal("0")) - return_.declared_turnover
        > KOBO_TOLERANCE
    ):
        findings.append(
            CorporateAuditFinding(
                "CIT_TURNOVER_MISMATCH",
                "error",
                (
                    f"Sum of revenue lines ({authoritative.total_revenue}) exceeds "
                    f"declared turnover ({return_.declared_turnover})."
                ),
                "declared_turnover",
            )
        )

    # 7. Heavy loss warning.
    if authoritative.computation is not None:
        turnover = authoritative.computation.annual_turnover
        profit = authoritative.computation.assessable_profit
        if turnover > 0 and profit < 0 and abs(profit) > turnover / 2:
            findings.append(
                CorporateAuditFinding(
                    "CIT_HEAVY_LOSS",
                    "warn",
                    (
                        f"Declared loss ({profit}) exceeds half of turnover "
                        f"({turnover}). Confirm the numbers before filing."
                    ),
                    "expenses",
                )
            )

    # 8. Declaration.
    if not return_.declaration:
        findings.append(
            CorporateAuditFinding(
                "CIT_DECLARATION_NOT_AFFIRMED",
                "error",
                "Authorised officer has not affirmed the declaration.",
                "declaration",
            )
        )

    # 9. Supporting documents when payable.
    if (
        authoritative.net_payable is not None
        and authoritative.net_payable > 0
        and not return_.supporting_document_ids
    ):
        findings.append(
            CorporateAuditFinding(
                "CIT_SUPPORTING_DOCS_MISSING",
                "warn",
                (
                    "CIT is payable but no supporting documents are attached. "
                    "NRS typically expects audited financials on file."
                ),
                "supporting_document_ids",
            )
        )

    # 10. Placeholder-rates banner.
    if CIT_SOURCE.startswith("PLACEHOLDER"):
        findings.append(
            CorporateAuditFinding(
                "CIT_RATES_PLACEHOLDER",
                "warn",
                (
                    "CIT bands are still illustrative (placeholder). The "
                    "computed liability will not be accurate until the owner "
                    "replaces the statutory table with the confirmed 2026 "
                    "schedule."
                ),
                None,
            )
        )

    return CorporateAuditReport(
        status=_status_from_findings(findings), findings=findings
    )
