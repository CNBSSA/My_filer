"""YearlyFact CRUD + filing-fact auto-capture (P8.2).

A `YearlyFact` is the atomic unit of Role 8 (Learning Partner): one
labelled, year-tagged fact about a taxpayer (gross income, PIT payable,
effective rate, etc.). Facts land automatically when a filing is
accepted / simulated by the gateway service; callers can also record
user-declared facts directly.

Values are stored as strings to preserve Decimal precision across
Postgres NUMERIC and SQLite TEXT without a driver dance.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.db.models import Filing, YearlyFact
from app.memory.embeddings.base import EmbeddingsError
from app.memory.embeddings.factory import build_embeddings_provider

log = logging.getLogger("mai_filer.memory.facts")


FACT_TYPES = {
    # Money facts.
    "annual_gross_income",
    "total_deductions",
    "chargeable_income",
    "total_tax",
    "paye_already_withheld",
    "net_payable",
    # Derived rates / counts.
    "effective_rate",
    "income_source_count",
    "supporting_document_count",
    # Submission receipts.
    "nrs_irn",
    "nrs_csid",
    "nrs_submission_status",
    # Free-form.
    "note",
}


def record_fact(
    session: Session,
    *,
    user_nin_hash: str | None,
    tax_year: int,
    fact_type: str,
    value: Decimal | int | str | float | bool | None,
    value_kind: str | None = None,
    unit: str = "NGN",
    source: str = "filing",
    label: str | None = None,
    meta: dict[str, Any] | None = None,
    filing_id: str | None = None,
) -> YearlyFact:
    """Persist a single fact. Values are stringified with kind inferred if
    not supplied.
    """
    if value is None:
        stored_value = ""
        kind = value_kind or "text"
    elif isinstance(value, bool):
        stored_value = "true" if value else "false"
        kind = value_kind or "text"
    elif isinstance(value, Decimal):
        stored_value = f"{value:f}"
        kind = value_kind or "decimal"
    elif isinstance(value, int):
        stored_value = str(value)
        kind = value_kind or "count"
    elif isinstance(value, float):
        stored_value = f"{Decimal(str(value)):f}"
        kind = value_kind or "decimal"
    else:
        stored_value = str(value)
        kind = value_kind or "text"

    fact = YearlyFact(
        user_nin_hash=user_nin_hash,
        filing_id=filing_id,
        tax_year=tax_year,
        fact_type=fact_type,
        value=stored_value,
        value_kind=kind,
        unit=unit,
        source=source,
        label=label,
        meta_json=meta,
    )
    _attach_embedding(fact)
    session.add(fact)
    session.flush()
    return fact


def _fact_embed_text(fact: YearlyFact) -> str:
    """Compact natural-language description of a fact for the embedder."""
    parts: list[str] = [
        f"tax year {fact.tax_year}",
        f"fact {fact.fact_type}",
    ]
    if fact.label:
        parts.append(fact.label)
    if fact.value:
        parts.append(f"value {fact.value} {fact.unit}")
    if fact.source:
        parts.append(f"source {fact.source}")
    return " · ".join(parts)


def _attach_embedding(fact: YearlyFact) -> None:
    """Best-effort embed. Failures never block a fact write."""
    provider = build_embeddings_provider()
    if provider.name == "noop":
        return
    try:
        result = provider.embed(_fact_embed_text(fact))
    except EmbeddingsError as exc:
        log.warning("embedding skipped for fact (non-fatal): %s", exc)
        return
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding skipped for fact (unexpected): %s", exc)
        return
    if result is None:
        return
    fact.embedding_json = json.dumps(result.vector)
    fact.embedding_model = result.model
    fact.embedding_dim = result.dimensions


def record_filing_facts(
    session: Session,
    *,
    filing: Filing,
    user_nin_hash: str | None,
    source: str,
) -> list[YearlyFact]:
    """Capture the salient facts from a finalized filing.

    Called by the gateway service when a submission reaches `accepted`
    or `simulated` status. Facts are idempotent per (nin_hash, year,
    fact_type, source) — duplicates are skipped so re-submission doesn't
    create noise.

    The filing's stored `return_json` may be sparse (the user-authored
    return, without authoritative totals). We route through
    `build_canonical_pack` to get computed figures, mirroring what the
    gateway service signs + ships to NRS.
    """
    # Local import avoids a module-level cycle (filing.serialize imports
    # tax + filing.schemas; memory.facts is agnostic at import time).
    from app.filing.schemas import PITReturn
    from app.filing.serialize import build_canonical_pack

    return_json = filing.return_json or {}
    tax_year = int(return_json.get("tax_year") or filing.tax_year)

    try:
        return_model = PITReturn.model_validate(return_json)
        pack = build_canonical_pack(return_model)
    except Exception:
        pack = None

    if pack is not None:
        income_block = pack.get("income") or {}
        computation = pack.get("computation") or {}
        settlement = pack.get("settlement") or {}
        sources_list = income_block.get("sources") or []
        docs = pack.get("supporting_document_ids") or []
        gross = income_block.get("total_gross")
        withheld = settlement.get("paye_already_withheld")
        net_payable = settlement.get("net_payable")
    else:
        computation = return_json.get("computation") or {}
        sources_list = return_json.get("income_sources") or []
        docs = return_json.get("supporting_document_ids") or []
        gross = return_json.get("total_gross_income")
        withheld = return_json.get("paye_already_withheld")
        net_payable = return_json.get("net_payable")

    planned: list[tuple[str, Any, str, str]] = [
        ("annual_gross_income",         gross,                                   "decimal", "NGN"),
        ("total_deductions",            computation.get("total_deductions"),     "decimal", "NGN"),
        ("chargeable_income",           computation.get("chargeable_income"),    "decimal", "NGN"),
        ("total_tax",                   computation.get("total_tax"),            "decimal", "NGN"),
        ("paye_already_withheld",       withheld,                                "decimal", "NGN"),
        ("net_payable",                 net_payable,                             "decimal", "NGN"),
        ("effective_rate",              computation.get("effective_rate"),       "rate",    "ratio"),
        ("income_source_count",         len(sources_list),                       "count",   "n"),
        ("supporting_document_count",   len(docs),                               "count",   "n"),
    ]

    # Receipt facts when we have them.
    if filing.nrs_irn:
        planned.append(("nrs_irn", filing.nrs_irn, "text", "id"))
    if filing.nrs_csid:
        planned.append(("nrs_csid", filing.nrs_csid, "text", "id"))
    planned.append(
        ("nrs_submission_status", filing.submission_status, "text", "status")
    )

    existing = {
        (row.fact_type, row.source)
        for row in _facts_for_year(
            session, user_nin_hash=user_nin_hash, tax_year=tax_year
        )
    }

    written: list[YearlyFact] = []
    for fact_type, value, kind, unit in planned:
        key = (fact_type, source)
        if key in existing:
            continue
        if value in (None, ""):
            continue
        written.append(
            record_fact(
                session,
                user_nin_hash=user_nin_hash,
                tax_year=tax_year,
                fact_type=fact_type,
                value=value,
                value_kind=kind,
                unit=unit,
                source=source,
                filing_id=filing.id,
            )
        )
    session.flush()
    return written


def _facts_for_year(
    session: Session, *, user_nin_hash: str | None, tax_year: int
) -> Iterable[YearlyFact]:
    q = session.query(YearlyFact).filter(YearlyFact.tax_year == tax_year)
    if user_nin_hash is None:
        q = q.filter(YearlyFact.user_nin_hash.is_(None))
    else:
        q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)
    return q.all()


def list_facts(
    session: Session,
    *,
    user_nin_hash: str | None = None,
    tax_year: int | None = None,
    fact_type: str | None = None,
    limit: int = 200,
) -> list[YearlyFact]:
    q = session.query(YearlyFact).order_by(
        YearlyFact.tax_year.desc(), YearlyFact.recorded_at.desc()
    )
    if user_nin_hash is not None:
        q = q.filter(YearlyFact.user_nin_hash == user_nin_hash)
    if tax_year is not None:
        q = q.filter(YearlyFact.tax_year == tax_year)
    if fact_type is not None:
        q = q.filter(YearlyFact.fact_type == fact_type)
    return q.limit(max(1, min(limit, 500))).all()


def fact_to_dict(fact: YearlyFact) -> dict[str, Any]:
    return {
        "id": fact.id,
        "tax_year": fact.tax_year,
        "fact_type": fact.fact_type,
        "value": fact.value,
        "value_kind": fact.value_kind,
        "unit": fact.unit,
        "source": fact.source,
        "label": fact.label,
        "meta": fact.meta_json,
        "recorded_at": fact.recorded_at.isoformat(),
        "filing_id": fact.filing_id,
    }
