"""Mai Filer tool registry — Phase 2 slice.

Each tool is a small, typed function backed by a pure calculator in
`apps/api/app/tax/`. The tool exposes:

  - `name`   : Claude tool name (stable).
  - `schema` : JSON schema Claude sees (tools API).
  - `run`    : pure Python callable with validated inputs.

The orchestrator's tool-use loop hands Claude the `schema`, receives
`tool_use` blocks, invokes `run(**args)`, and feeds the JSON result back as
`tool_result`. No business logic lives inside the orchestrator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from app.db.models import Document, Filing
from app.db.session import get_session
from app.documents.storage import get_default_storage
from app.filing.corporate_audit import audit as run_corporate_audit
from app.filing.corporate_schemas import CITReturn
from app.filing.corporate_service import (
    audit_corporate_filing,
    create_corporate_filing,
    generate_corporate_pack,
)
from app.filing.ngo_audit import audit as run_ngo_audit
from app.filing.ngo_schemas import NGOReturn
from app.filing.ngo_service import (
    audit_ngo_filing,
    create_ngo_filing,
    generate_ngo_pack,
)
from app.filing.service import PackNotReadyError, audit_filing, generate_pack
from app.gateway.service import SubmissionConfigError, submit_filing_to_nrs
from app.identity.base import AggregatorError
from app.identity.factory import build_identity_service
from app.identity.service import ConsentRequiredError
from app.filing.ubl import UBLEnvelope, validate_envelope
from app.memory.anomalies import detect_anomalies
from app.memory.facts import fact_to_dict, list_facts
from app.memory.nudges import suggest_nudges
from app.memory.recall_factory import build_recall
from app.tax.cit import calculate_cit_2026
from app.tax.dev_levy import calculate_dev_levy
from app.tax.paye import calculate_paye
from app.tax.pit import calculate_pit_2026
from app.tax.reliefs import ReliefScenario, explore_reliefs
from app.tax.statutory import (
    CIT_SOURCE,
    NGO_EXEMPT_PURPOSES,
    NGO_RULES_SOURCE,
    UBL_SOURCE,
    WHT_SOURCE,
    is_placeholder,
)
from app.tax.vat import (
    calculate_vat,
    distance_to_threshold,
    is_vat_registrable,
)
from app.tax.wht import calculate_wht, known_transaction_classes

# ---------------------------------------------------------------------------
# Serialization helpers — Decimal is not JSON-safe.
# ---------------------------------------------------------------------------


def _d(value: Decimal) -> str:
    """Render a Decimal as a plain string so the downstream LLM can quote it
    without float drift."""
    return f"{value:f}"


def _pit_payload(result) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "annual_income": _d(result.annual_income),
        "total_tax": _d(result.total_tax),
        "effective_rate": _d(result.effective_rate),
        "take_home": _d(result.take_home),
        "bands": [
            {
                "order": b.band.order,
                "name": b.band.name,
                "rate": _d(b.band.rate),
                "taxable_amount": _d(b.taxable_amount),
                "tax_amount": _d(b.tax_amount),
            }
            for b in result.bands
        ],
    }


def _paye_payload(result) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "annual_gross": _d(result.annual_gross),
        "deductions": {
            "pension": _d(result.deductions.pension),
            "nhis": _d(result.deductions.nhis),
            "cra": _d(result.deductions.cra),
            "other_reliefs": _d(result.deductions.other_reliefs),
            "total": _d(result.deductions.total),
        },
        "chargeable_income": _d(result.chargeable_income),
        "annual_tax": _d(result.annual_tax),
        "monthly_tax": _d(result.monthly_tax),
        "take_home_annual": _d(result.take_home_annual),
        "take_home_monthly": _d(result.take_home_monthly),
        "pit": _pit_payload(result.pit),
    }


# ---------------------------------------------------------------------------
# Tool runners
# ---------------------------------------------------------------------------


def _run_calc_pit(annual_income: float | int | str) -> dict[str, Any]:
    result = calculate_pit_2026(Decimal(str(annual_income)))
    return _pit_payload(result)


def _run_calc_paye(
    annual_gross: float | int | str,
    pension: float | int | str = 0,
    nhis: float | int | str = 0,
    cra: float | int | str = 0,
    other_reliefs: float | int | str = 0,
) -> dict[str, Any]:
    result = calculate_paye(
        Decimal(str(annual_gross)),
        pension=Decimal(str(pension)),
        nhis=Decimal(str(nhis)),
        cra=Decimal(str(cra)),
        other_reliefs=Decimal(str(other_reliefs)),
    )
    return _paye_payload(result)


def _run_explore_reliefs(
    annual_gross: float | int | str,
    scenarios: list[dict[str, Any]],
    baseline_pension: float | int | str = 0,
    baseline_nhis: float | int | str = 0,
    baseline_cra: float | int | str = 0,
    baseline_other_reliefs: float | int | str = 0,
) -> dict[str, Any]:
    parsed = [
        ReliefScenario(category=s["category"], amount=Decimal(str(s["amount"])))
        for s in scenarios
    ]
    baseline, outcomes = explore_reliefs(
        Decimal(str(annual_gross)),
        baseline_pension=Decimal(str(baseline_pension)),
        baseline_nhis=Decimal(str(baseline_nhis)),
        baseline_cra=Decimal(str(baseline_cra)),
        baseline_other_reliefs=Decimal(str(baseline_other_reliefs)),
        scenarios=parsed,
    )
    return {
        "baseline": _paye_payload(baseline),
        "outcomes": [
            {
                "category": o.scenario.category,
                "amount": _d(o.scenario.amount),
                "baseline_tax": _d(o.baseline_tax),
                "projected_tax": _d(o.projected_tax),
                "tax_saved": _d(o.tax_saved),
                "projected_chargeable": _d(o.projected_chargeable),
            }
            for o in outcomes
        ],
    }


def _run_calc_vat(
    taxable_supply: float | int | str,
    exempt_supply: float | int | str = 0,
    input_vat: float | int | str = 0,
) -> dict[str, Any]:
    result = calculate_vat(
        Decimal(str(taxable_supply)),
        exempt_supply=Decimal(str(exempt_supply)),
        input_vat=Decimal(str(input_vat)),
    )
    return {
        "taxable_supply": _d(result.taxable_supply),
        "exempt_supply": _d(result.exempt_supply),
        "rate": _d(result.rate),
        "output_vat": _d(result.output_vat),
        "input_vat": _d(result.input_vat),
        "net_vat_payable": _d(result.net_vat_payable),
        "total_supply": _d(result.total_supply),
    }


def _run_check_vat_registrable(annual_turnover: float | int | str) -> dict[str, Any]:
    turnover = Decimal(str(annual_turnover))
    return {
        "annual_turnover": _d(turnover),
        "is_registrable": is_vat_registrable(turnover),
        "threshold": "100000000.00",
        "distance_to_threshold": _d(distance_to_threshold(turnover)),
    }


def _run_calc_dev_levy(assessable_profit: float | int | str) -> dict[str, Any]:
    levy = calculate_dev_levy(Decimal(str(assessable_profit)))
    return {"assessable_profit": _d(Decimal(str(assessable_profit))), "levy": _d(levy)}


# ---------------------------------------------------------------------------
# Corporate tools (Phase 9 — CIT / WHT / UBL)
# ---------------------------------------------------------------------------


def _run_calc_cit(
    annual_turnover: float | int | str,
    assessable_profit: float | int | str,
    include_tertiary: bool = True,
) -> dict[str, Any]:
    result = calculate_cit_2026(
        annual_turnover=Decimal(str(annual_turnover)),
        assessable_profit=Decimal(str(assessable_profit)),
        include_tertiary=include_tertiary,
    )
    return {
        "annual_turnover": _d(result.annual_turnover),
        "assessable_profit": _d(result.assessable_profit),
        "tier": result.tier,
        "cit_rate": _d(result.cit_rate),
        "cit_amount": _d(result.cit_amount),
        "tertiary_rate": _d(result.tertiary_rate),
        "tertiary_amount": _d(result.tertiary_amount),
        "total_payable": _d(result.total_payable),
        "notes": list(result.notes),
        "statutory_source": CIT_SOURCE,
        "statutory_is_placeholder": is_placeholder(CIT_SOURCE),
    }


def _run_calc_wht(
    gross_amount: float | int | str,
    transaction_class: str,
) -> dict[str, Any]:
    try:
        result = calculate_wht(
            gross_amount=Decimal(str(gross_amount)),
            transaction_class=transaction_class,
        )
    except ValueError as exc:
        return {
            "error": str(exc),
            "known_classes": known_transaction_classes(),
            "statutory_source": WHT_SOURCE,
            "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
        }
    return {
        "transaction_class": result.transaction_class,
        "gross_amount": _d(result.gross_amount),
        "wht_rate": _d(result.wht_rate),
        "wht_amount": _d(result.wht_amount),
        "net_payable": _d(result.net_payable),
        "statutory_source": WHT_SOURCE,
        "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
    }


def _run_list_wht_classes() -> dict[str, Any]:
    return {
        "classes": known_transaction_classes(),
        "statutory_source": WHT_SOURCE,
        "statutory_is_placeholder": is_placeholder(WHT_SOURCE),
    }


# ---------------------------------------------------------------------------
# NGO tools (Phase 11)
# ---------------------------------------------------------------------------


def _run_list_ngo_exempt_purposes() -> dict[str, Any]:
    return {
        "purposes": list(NGO_EXEMPT_PURPOSES),
        "statutory_source": NGO_RULES_SOURCE,
        "statutory_is_placeholder": is_placeholder(NGO_RULES_SOURCE),
    }


def _run_audit_ngo_filing(filing_id: str) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return {"error": f"filing not found: {filing_id}"}
        if filing.tax_kind != "ngo_annual":
            return {
                "error": (
                    f"filing {filing_id} is tax_kind={filing.tax_kind!r} — "
                    "audit_ngo_filing only handles 'ngo_annual'. Use "
                    "audit_filing for PIT."
                ),
                "reason": "tax_kind_mismatch",
            }
        report = audit_ngo_filing(session=session, filing=filing)
        return {
            "filing_id": filing.id,
            "tax_year": filing.tax_year,
            "tax_kind": filing.tax_kind,
            "status": report.status,
            "findings": [f.to_dict() for f in report.findings],
            "statutory_source": NGO_RULES_SOURCE,
            "statutory_is_placeholder": is_placeholder(NGO_RULES_SOURCE),
        }
    finally:
        session_gen.close()


def _run_audit_corporate_filing(filing_id: str) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return {"error": f"filing not found: {filing_id}"}
        if filing.tax_kind != "cit":
            return {
                "error": (
                    f"filing {filing_id} is tax_kind={filing.tax_kind!r} — "
                    "audit_corporate_filing only handles 'cit'. Use "
                    "audit_filing (PIT) or audit_ngo_filing (NGO)."
                ),
                "reason": "tax_kind_mismatch",
            }
        report = audit_corporate_filing(session=session, filing=filing)
        return {
            "filing_id": filing.id,
            "tax_year": filing.tax_year,
            "tax_kind": filing.tax_kind,
            "status": report.status,
            "findings": [f.to_dict() for f in report.findings],
            "statutory_source": CIT_SOURCE,
            "statutory_is_placeholder": is_placeholder(CIT_SOURCE),
        }
    finally:
        session_gen.close()


def _run_audit_corporate_return(return_: dict[str, Any]) -> dict[str, Any]:
    """Audit a CIT return payload without persisting it.

    Mai uses this during conversational drafting — surface findings from
    the in-memory dict before committing to a saved filing. The
    computation is run against the placeholder CIT bands; the
    `statutory_is_placeholder` flag in the response tells Mai to caveat
    any liability figure she quotes.
    """
    try:
        typed = CITReturn.model_validate(return_)
    except Exception as exc:
        return {"error": f"return failed schema parse: {exc}"}
    report = run_corporate_audit(typed)
    return {
        "status": report.status,
        "findings": [f.to_dict() for f in report.findings],
        "statutory_source": CIT_SOURCE,
        "statutory_is_placeholder": is_placeholder(CIT_SOURCE),
    }


def _run_audit_ngo_return(return_: dict[str, Any]) -> dict[str, Any]:
    """Audit an NGO return payload without persisting it.

    Useful when Mai is helping a user draft a return in-conversation —
    she can run the Audit Shield against the in-memory dict and surface
    findings before the user commits to creating a filing.
    """
    try:
        typed = NGOReturn.model_validate(return_)
    except Exception as exc:
        return {"error": f"return failed schema parse: {exc}"}
    report = run_ngo_audit(typed)
    return {
        "status": report.status,
        "findings": [f.to_dict() for f in report.findings],
        "statutory_source": NGO_RULES_SOURCE,
        "statutory_is_placeholder": is_placeholder(NGO_RULES_SOURCE),
    }


# ---------------------------------------------------------------------------
# Memory tools (Phase 8 — Learning Partner)
# ---------------------------------------------------------------------------


def _run_list_user_facts(
    nin_hash: str | None = None,
    tax_year: int | None = None,
    fact_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        rows = list_facts(
            session,
            user_nin_hash=nin_hash,
            tax_year=tax_year,
            fact_type=fact_type,
            limit=limit,
        )
        return {"facts": [fact_to_dict(r) for r in rows]}
    finally:
        session_gen.close()


def _run_recall_memory(
    query: str,
    nin_hash: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        recaller = build_recall(session)
        rows = recaller.recall(user_nin_hash=nin_hash, query=query, limit=limit)
        return {
            "facts": [fact_to_dict(r) for r in rows],
            "mode": recaller.__class__.__name__,
        }
    finally:
        session_gen.close()


def _run_detect_yoy_anomalies(
    current_year: int,
    nin_hash: str | None = None,
    prior_year: int | None = None,
) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        findings = detect_anomalies(
            session,
            user_nin_hash=nin_hash,
            current_year=current_year,
            prior_year=prior_year,
        )
        return {"findings": [f.to_dict() for f in findings]}
    finally:
        session_gen.close()


def _run_suggest_mid_year_nudges(
    current_year: int,
    ytd_gross: float | int | str,
    month: int,
    nin_hash: str | None = None,
    prior_year: int | None = None,
) -> dict[str, Any]:
    session_gen = get_session()
    session = next(session_gen)
    try:
        items = suggest_nudges(
            session,
            user_nin_hash=nin_hash,
            current_year=current_year,
            ytd_gross=Decimal(str(ytd_gross)),
            month=month,
            prior_year=prior_year,
        )
        return {"nudges": [n.to_dict() for n in items]}
    finally:
        session_gen.close()


def _run_validate_ubl_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Run structural validation over a proposed UBL 3.0 envelope."""
    try:
        typed = UBLEnvelope.model_validate(envelope)
    except Exception as exc:
        return {
            "error": f"envelope failed schema parse: {exc}",
            "statutory_source": UBL_SOURCE,
            "statutory_is_placeholder": is_placeholder(UBL_SOURCE),
        }
    report = validate_envelope(typed)
    payload = report.to_dict()
    payload["statutory_source"] = UBL_SOURCE
    payload["statutory_is_placeholder"] = is_placeholder(UBL_SOURCE)
    return payload


# ---------------------------------------------------------------------------
# Document tools (Phase 3)
# ---------------------------------------------------------------------------


def _run_list_recent_documents(limit: int = 10) -> dict[str, Any]:
    """List recent uploaded documents with their kind + extraction status.

    Uses a short-lived DB session so the tool stays callable from anywhere
    (tests override `app.db.session.get_session` via dependency injection;
    calling `next(get_session())` here respects that override).
    """
    session_gen = get_session()
    session = next(session_gen)
    try:
        rows = (
            session.query(Document)
            .order_by(Document.created_at.desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )
        return {
            "documents": [
                {
                    "id": doc.id,
                    "kind": doc.kind,
                    "filename": doc.filename,
                    "content_type": doc.content_type,
                    "size_bytes": doc.size_bytes,
                    "has_extraction": doc.extraction_json is not None,
                    "extraction_error": doc.extraction_error,
                    "created_at": doc.created_at.isoformat(),
                }
                for doc in rows
            ]
        }
    finally:
        session_gen.close()


def _run_read_document_extraction(document_id: str) -> dict[str, Any]:
    """Return the structured extraction for a document, if any."""
    session_gen = get_session()
    session = next(session_gen)
    try:
        doc = session.get(Document, document_id)
        if doc is None:
            return {"error": f"document not found: {document_id}"}
        return {
            "id": doc.id,
            "kind": doc.kind,
            "filename": doc.filename,
            "extraction": doc.extraction_json,
            "extraction_error": doc.extraction_error,
        }
    finally:
        session_gen.close()


# ---------------------------------------------------------------------------
# Filing tools (Phase 4)
# ---------------------------------------------------------------------------


def _run_audit_filing(filing_id: str) -> dict[str, Any]:
    """Run Audit Shield on a filing and return the full report.

    Mai Filer must call this before offering a pack download — she refuses to
    finalize a filing that is still red, per ROLES.md Role 6 (Audit Shield).
    """
    session_gen = get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return {"error": f"filing not found: {filing_id}"}
        report = audit_filing(session=session, filing=filing)
        return {
            "filing_id": filing.id,
            "tax_year": filing.tax_year,
            "status": report.status,
            "findings": [f.to_dict() for f in report.findings],
        }
    finally:
        session_gen.close()


def _run_prepare_filing_pack(filing_id: str) -> dict[str, Any]:
    """Build the downloadable JSON + PDF pack for a filing.

    Runs Audit Shield first. If status is 'red', returns an error so Mai can
    explain what to fix before retrying. Otherwise returns the pack summary
    and the download URLs (the pack itself is persisted on the filing row).
    """
    session_gen = get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return {"error": f"filing not found: {filing_id}"}
        try:
            pack = generate_pack(
                session=session, storage=get_default_storage(), filing=filing
            )
        except PackNotReadyError as exc:
            return {
                "error": str(exc),
                "audit_status": filing.audit_status,
                "audit": filing.audit_json,
            }
        return {
            "filing_id": filing.id,
            "tax_year": filing.tax_year,
            "audit_status": filing.audit_status,
            "settlement": pack["settlement"],
            "total_tax": pack["computation"]["total_tax"],
            "download_urls": {
                "pdf": f"/v1/filings/{filing.id}/pack.pdf",
                "json": f"/v1/filings/{filing.id}/pack.json",
            },
            "finalized_at": filing.finalized_at.isoformat() if filing.finalized_at else None,
        }
    finally:
        session_gen.close()


def _run_submit_to_nrs(filing_id: str, language: str = "en") -> dict[str, Any]:
    """Submit a finalized filing to NRS (or to the simulation path if
    credentials are missing). Never bypass the Audit Shield — the service
    refuses red / pending audits."""
    session_gen = get_session()
    session = next(session_gen)
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return {"error": f"filing not found: {filing_id}"}
        try:
            outcome = submit_filing_to_nrs(
                session=session, filing=filing, language=language
            )
        except SubmissionConfigError as exc:
            return {"error": str(exc), "reason": "not_ready_for_submission"}
        return outcome.to_dict()
    finally:
        session_gen.close()


def _run_verify_identity(
    nin: str,
    consent: bool,
    declared_name: str | None = None,
    purpose: str = "tax_filing",
) -> dict[str, Any]:
    """Look up a NIN via the configured aggregator (Dojah by default).

    This tool is the ONLY place Mai should query a NIN. It enforces the
    `consent` flag, hashes the NIN, vaults the ciphertext on success, and
    writes an append-only consent_log row regardless of outcome.
    """
    session_gen = get_session()
    session = next(session_gen)
    try:
        service = build_identity_service(session)
        try:
            result = service.verify_taxpayer(
                nin=nin,
                consent=consent,
                declared_name=declared_name,
                purpose=purpose,
            )
        except ConsentRequiredError as exc:
            return {"error": str(exc), "reason": "consent_required"}
        except ValueError as exc:
            return {"error": str(exc), "reason": "invalid_input"}
        except AggregatorError as exc:
            return {"error": str(exc), "reason": "aggregator_unavailable"}
        return result.to_dict()
    finally:
        session_gen.close()


def _run_verify_cac(
    rc_number: str,
    consent: bool,
    declared_name: str | None = None,
    purpose: str = "corporate_filing",
) -> dict[str, Any]:
    """Look up a CAC RC number via the configured aggregator (Dojah default).

    Same consent contract as `verify_identity`: only call this after the
    authorized officer has explicitly agreed on-chat. The service writes
    an append-only consent_log row and upserts a `cac_records` snapshot
    on success so the corporate filing flow can cross-check the taxpayer.
    """
    session_gen = get_session()
    session = next(session_gen)
    try:
        service = build_identity_service(session)
        try:
            result = service.verify_organization(
                rc_number=rc_number,
                consent=consent,
                declared_name=declared_name,
                purpose=purpose,
            )
        except ConsentRequiredError as exc:
            return {"error": str(exc), "reason": "consent_required"}
        except ValueError as exc:
            return {"error": str(exc), "reason": "invalid_input"}
        except AggregatorError as exc:
            return {"error": str(exc), "reason": "aggregator_unavailable"}
        return result.to_dict()
    finally:
        session_gen.close()


def _run_list_recent_filings(limit: int = 10) -> dict[str, Any]:
    """List the most recent filings — useful when a user refers to 'my filing'."""
    session_gen = get_session()
    session = next(session_gen)
    try:
        rows = (
            session.query(Filing)
            .order_by(Filing.created_at.desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )
        return {
            "filings": [
                {
                    "id": f.id,
                    "tax_year": f.tax_year,
                    "audit_status": f.audit_status,
                    "pack_ready": bool(f.pack_pdf_key and f.pack_json_key),
                    "created_at": f.created_at.isoformat(),
                    "finalized_at": f.finalized_at.isoformat() if f.finalized_at else None,
                }
                for f in rows
            ]
        }
    finally:
        session_gen.close()


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[..., dict[str, Any]]


TOOLS: tuple[Tool, ...] = (
    Tool(
        name="calc_pit",
        description=(
            "Compute Personal Income Tax (PIT) on annual income using the 2026 "
            "Nigerian bands. Returns total tax, effective rate, and a per-band "
            "breakdown. Use this when the user asks for PIT on a naira amount."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "annual_income": {
                    "type": "number",
                    "description": "Annual income in Nigerian naira (₦). Must be >= 0.",
                }
            },
            "required": ["annual_income"],
        },
        run=_run_calc_pit,
    ),
    Tool(
        name="calc_paye",
        description=(
            "Compute PAYE tax on employment income after deductions "
            "(pension, NHIS, CRA, other reliefs). All amounts are annual naira. "
            "Use this when the user gives payslip or salary details."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "annual_gross": {"type": "number"},
                "pension": {"type": "number", "default": 0},
                "nhis": {"type": "number", "default": 0},
                "cra": {"type": "number", "default": 0},
                "other_reliefs": {"type": "number", "default": 0},
            },
            "required": ["annual_gross"],
        },
        run=_run_calc_paye,
    ),
    Tool(
        name="explore_reliefs",
        description=(
            "Project PAYE savings from candidate reliefs. Each scenario is "
            "independent; amounts are absolute naira additions to the user's "
            "deductions. Categories: 'pension_topup' adds to pension; any other "
            "label (e.g. 'life_insurance', 'nhf') adds to other_reliefs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "annual_gross": {"type": "number"},
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "amount": {"type": "number"},
                        },
                        "required": ["category", "amount"],
                    },
                },
                "baseline_pension": {"type": "number", "default": 0},
                "baseline_nhis": {"type": "number", "default": 0},
                "baseline_cra": {"type": "number", "default": 0},
                "baseline_other_reliefs": {"type": "number", "default": 0},
            },
            "required": ["annual_gross", "scenarios"],
        },
        run=_run_explore_reliefs,
    ),
    Tool(
        name="calc_vat",
        description=(
            "Compute VAT at the 2026 standard rate (7.5%). Takes taxable "
            "supply, optional exempt supply and input-VAT credit. Returns "
            "output VAT, input VAT, and net VAT payable."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "taxable_supply": {"type": "number"},
                "exempt_supply": {"type": "number", "default": 0},
                "input_vat": {"type": "number", "default": 0},
            },
            "required": ["taxable_supply"],
        },
        run=_run_calc_vat,
    ),
    Tool(
        name="check_vat_registrable",
        description=(
            "Check whether an entity must register for VAT based on the ₦100m "
            "annual-turnover threshold (NTAA 2026). Returns a boolean and the "
            "distance to the threshold."
        ),
        input_schema={
            "type": "object",
            "properties": {"annual_turnover": {"type": "number"}},
            "required": ["annual_turnover"],
        },
        run=_run_check_vat_registrable,
    ),
    Tool(
        name="calc_dev_levy",
        description=(
            "Compute the 4% Development Levy on assessable profit. This is "
            "corporate (v2 scope); use only when explicitly asked about a "
            "company's levy."
        ),
        input_schema={
            "type": "object",
            "properties": {"assessable_profit": {"type": "number"}},
            "required": ["assessable_profit"],
        },
        run=_run_calc_dev_levy,
    ),
    Tool(
        name="list_recent_documents",
        description=(
            "List the most recently uploaded documents the user has shared. "
            "Use this when the user refers to a payslip or receipt they just "
            "uploaded, to find its id before reading its extraction."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}
            },
        },
        run=_run_list_recent_documents,
    ),
    Tool(
        name="read_document_extraction",
        description=(
            "Fetch the structured extraction for a specific document by id. "
            "Returns the fields extracted by the vision pipeline (e.g. for a "
            "payslip: gross_income, pension, PAYE withheld, etc). Use the "
            "extraction numbers as inputs to calc_paye."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document."}
            },
            "required": ["document_id"],
        },
        run=_run_read_document_extraction,
    ),
    Tool(
        name="audit_filing",
        description=(
            "Run the Audit Shield on a filing by id. Returns status "
            "(green|yellow|red) and an itemized list of findings. You MUST run "
            "this before offering the taxpayer a downloadable pack; if the "
            "status is red, explain each finding and ask the user to fix it "
            "before retrying."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filing_id": {"type": "string", "description": "UUID of the filing."}
            },
            "required": ["filing_id"],
        },
        run=_run_audit_filing,
    ),
    Tool(
        name="prepare_filing_pack",
        description=(
            "Build the downloadable NRS-ready pack (JSON + PDF) for a filing. "
            "Runs Audit Shield internally; if status is red the tool returns an "
            "error payload — do NOT invent a download URL in that case. On "
            "success, surface the download URLs in your reply so the UI can "
            "link them."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filing_id": {"type": "string", "description": "UUID of the filing."}
            },
            "required": ["filing_id"],
        },
        run=_run_prepare_filing_pack,
    ),
    Tool(
        name="list_recent_filings",
        description=(
            "List the most recently created filings for the current session. "
            "Use this when the user says 'my filing' or 'the return' without "
            "specifying an id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}
            },
        },
        run=_run_list_recent_filings,
    ),
    Tool(
        name="calc_cit",
        description=(
            "Compute Corporate Income Tax + tertiary education levy on a "
            "Nigerian company's return. Takes annual_turnover (determines "
            "tier) and assessable_profit. Returns the tier, rate, CIT "
            "amount, tertiary amount, and total payable. The response also "
            "tells you whether the underlying statutory table is still a "
            "placeholder — if so, caveat your answer clearly and do NOT "
            "treat the figure as authoritative for the 2026 year."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "annual_turnover": {"type": "number"},
                "assessable_profit": {"type": "number"},
                "include_tertiary": {"type": "boolean", "default": True},
            },
            "required": ["annual_turnover", "assessable_profit"],
        },
        run=_run_calc_cit,
    ),
    Tool(
        name="calc_wht",
        description=(
            "Compute Withholding Tax and net payable for a given "
            "transaction class and gross amount. Unknown classes return "
            "an error listing the known classes. Statutory source is "
            "surfaced so you can caveat when it's still a placeholder."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "gross_amount": {"type": "number"},
                "transaction_class": {
                    "type": "string",
                    "description": (
                        "One of the known WHT classes. Call list_wht_classes "
                        "first if unsure."
                    ),
                },
            },
            "required": ["gross_amount", "transaction_class"],
        },
        run=_run_calc_wht,
    ),
    Tool(
        name="list_wht_classes",
        description=(
            "Return the known WHT transaction classes from the current "
            "statutory table."
        ),
        input_schema={"type": "object", "properties": {}},
        run=_run_list_wht_classes,
    ),
    Tool(
        name="validate_ubl_envelope",
        description=(
            "Structurally validate a proposed UBL 3.0 envelope: must have "
            "8 sections in canonical order and exactly 55 fields covering "
            "the current statutory list. Returns a findings list so you "
            "can tell the user what to fix before MBS submission."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "envelope": {
                    "type": "object",
                    "description": "The UBLEnvelope dict: {version, profile, sections: [...]}.",
                }
            },
            "required": ["envelope"],
        },
        run=_run_validate_ubl_envelope,
    ),
    Tool(
        name="list_ngo_exempt_purposes",
        description=(
            "Return the list of organisational purposes that currently "
            "qualify a Nigerian body for tax-exempt status. The response "
            "surfaces whether the underlying statutory table is still a "
            "placeholder — caveat any advice accordingly."
        ),
        input_schema={"type": "object", "properties": {}},
        run=_run_list_ngo_exempt_purposes,
    ),
    Tool(
        name="audit_ngo_filing",
        description=(
            "Run the NGO Audit Shield on an existing filing by id. Returns "
            "status (green|yellow|red) and findings. Use this before you "
            "offer the user a downloadable NGO pack. Rejects filings whose "
            "tax_kind is not 'ngo_annual'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filing_id": {"type": "string", "description": "UUID of the filing."}
            },
            "required": ["filing_id"],
        },
        run=_run_audit_ngo_filing,
    ),
    Tool(
        name="audit_ngo_return",
        description=(
            "Run the NGO Audit Shield against an NGO return dict that hasn't "
            "been saved yet. Use this while helping the user draft a return "
            "— you can surface findings conversationally before committing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "return_": {
                    "type": "object",
                    "description": "An NGOReturn payload (organization, income, expenditure, ...).",
                }
            },
            "required": ["return_"],
        },
        run=_run_audit_ngo_return,
    ),
    Tool(
        name="audit_corporate_filing",
        description=(
            "Run the Corporate (CIT) Audit Shield on an existing filing by "
            "id. Returns status (green|yellow|red) and findings. Use this "
            "before offering the user a downloadable CIT pack. Rejects "
            "filings whose tax_kind is not 'cit'. The response carries "
            "statutory_is_placeholder=true until the owner replaces the "
            "2026 CIT bands — always caveat your liability commentary "
            "accordingly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filing_id": {"type": "string", "description": "UUID of the filing."}
            },
            "required": ["filing_id"],
        },
        run=_run_audit_corporate_filing,
    ),
    Tool(
        name="audit_corporate_return",
        description=(
            "Run the Corporate (CIT) Audit Shield against a CITReturn dict "
            "that hasn't been saved yet. Great for helping a founder shape "
            "their return in-conversation — surface findings + illustrative "
            "liability before they commit to a filing row."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "return_": {
                    "type": "object",
                    "description": (
                        "A CITReturn payload (taxpayer, revenues, expenses, "
                        "declared_turnover?, declared_assessable_profit?, ...)."
                    ),
                }
            },
            "required": ["return_"],
        },
        run=_run_audit_corporate_return,
    ),
    Tool(
        name="submit_to_nrs",
        description=(
            "Submit a finalized filing to the Nigeria Revenue Service (NRS) "
            "via the signed HMAC-SHA256 gateway. Audit Shield must be green "
            "or yellow — the service refuses red. If NRS credentials aren't "
            "configured in the environment, the submission is *simulated* "
            "deterministically and the response will include `simulated: "
            "true` — surface this to the user so they know they're looking "
            "at a preview, not a real acknowledgement. On success you get "
            "an IRN (invoice reference number), CSID (cryptographic stamp), "
            "and QR payload; tell the user all three."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filing_id": {"type": "string", "description": "UUID of the filing."},
                "language": {
                    "type": "string",
                    "description": "Language for error messages. Defaults to 'en'.",
                    "default": "en",
                },
            },
            "required": ["filing_id"],
        },
        run=_run_submit_to_nrs,
    ),
    Tool(
        name="list_user_facts",
        description=(
            "List structured year-over-year facts Mai has stored about the "
            "taxpayer (gross income, PIT, effective rate, deductions, "
            "submission receipts). Use this when the user asks about their "
            "history; filter by `nin_hash`, `tax_year`, and/or `fact_type`."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nin_hash": {"type": ["string", "null"]},
                "tax_year": {"type": ["integer", "null"]},
                "fact_type": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            },
        },
        run=_run_list_user_facts,
    ),
    Tool(
        name="recall_memory",
        description=(
            "Keyword-based recall across the taxpayer's history. Pass a free-"
            "text `query` — matches are ranked by token coverage then "
            "recency. Use this when the user asks vague 'did I…' / 'what "
            "was that…' questions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "nin_hash": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
            },
            "required": ["query"],
        },
        run=_run_recall_memory,
    ),
    Tool(
        name="detect_yoy_anomalies",
        description=(
            "Compare this year's money-valued facts against last year's "
            "and return the significant deltas (watch: 25-50%, alert: 50%+). "
            "Call this before preparing a filing so you can proactively "
            "raise anything unusual."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "current_year": {"type": "integer"},
                "nin_hash": {"type": ["string", "null"]},
                "prior_year": {"type": ["integer", "null"]},
            },
            "required": ["current_year"],
        },
        run=_run_detect_yoy_anomalies,
    ),
    Tool(
        name="suggest_mid_year_nudges",
        description=(
            "Mid-year check-in. Given the taxpayer's YTD gross and the "
            "month they're through, annualize the figure and flag: "
            ">=30% YoY pace change (watch), PIT band crossings (alert), "
            "approach to or crossing of the ₦100m VAT threshold."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "current_year": {"type": "integer"},
                "ytd_gross": {"type": "number", "minimum": 0},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
                "nin_hash": {"type": ["string", "null"]},
                "prior_year": {"type": ["integer", "null"]},
            },
            "required": ["current_year", "ytd_gross", "month"],
        },
        run=_run_suggest_mid_year_nudges,
    ),
    Tool(
        name="verify_identity",
        description=(
            "Look up a NIN via the configured identity aggregator (Dojah by "
            "default) and return the NIMC identity record. You MUST only call "
            "this after the taxpayer has explicitly granted consent in the "
            "conversation — set `consent=true` only if you have heard their "
            "yes. If you also pass `declared_name`, the service compares it "
            "against the NIN record's name and returns a match status "
            "(strict / fuzzy / mismatch) that you should surface to the user. "
            "A consent-log row is written regardless of outcome (this is a "
            "regulatory requirement — NDPR / NDPC)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nin": {
                    "type": "string",
                    "description": "11-digit National Identification Number.",
                    "pattern": "^[0-9]{11}$",
                },
                "consent": {
                    "type": "boolean",
                    "description": "MUST be true. Set only after explicit user consent.",
                },
                "declared_name": {
                    "type": ["string", "null"],
                    "description": "The name the user told you — used for name-match.",
                },
                "purpose": {
                    "type": "string",
                    "description": "Short label for the consent log, e.g. 'tax_filing'.",
                    "default": "tax_filing",
                },
            },
            "required": ["nin", "consent"],
        },
        run=_run_verify_identity,
    ),
    Tool(
        name="verify_cac",
        description=(
            "Look up a CAC RC number on the Corporate Affairs Commission "
            "register via the configured aggregator. Use this for SME / "
            "corporate / NGO flows once the authorized officer has consented "
            "on-chat (NDPR rule). If you pass `declared_name` the service "
            "compares it against the registered company name and returns a "
            "match status (strict / fuzzy / mismatch) you should surface. "
            "A consent_log row is appended regardless of outcome, and on "
            "success a `cac_records` snapshot is upserted for later review."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "rc_number": {
                    "type": "string",
                    "description": "CAC registration number (alphanumeric).",
                    "minLength": 1,
                    "maxLength": 64,
                },
                "consent": {
                    "type": "boolean",
                    "description": "MUST be true. Set only after explicit consent.",
                },
                "declared_name": {
                    "type": ["string", "null"],
                    "description": "The company name the user declared — used for name-match.",
                },
                "purpose": {
                    "type": "string",
                    "description": "Short label for the consent log, e.g. 'corporate_filing'.",
                    "default": "corporate_filing",
                },
            },
            "required": ["rc_number", "consent"],
        },
        run=_run_verify_cac,
    ),
)

_TOOL_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}


def tool_schemas() -> list[dict[str, Any]]:
    """Return Claude tool descriptors."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS
    ]


def run_tool(name: str, arguments: dict[str, Any] | None) -> str:
    """Dispatch a tool call. Returns a JSON string (Claude's tool_result payload)."""
    tool = _TOOL_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        result = tool.run(**(arguments or {}))
    except Exception as exc:  # surface to Claude; never silently swallow
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def tool_names() -> list[str]:
    return [t.name for t in TOOLS]
