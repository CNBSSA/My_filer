"""Memory endpoints — surface Learning Partner data over HTTP."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.memory.anomalies import detect_anomalies
from app.memory.facts import fact_to_dict, list_facts
from app.memory.nudges import suggest_nudges
from app.memory.recall import KeywordRecall

router = APIRouter(prefix="/v1/memory", tags=["memory"])


@router.get("/facts")
async def get_facts(
    nin_hash: str | None = None,
    tax_year: int | None = None,
    fact_type: str | None = None,
    limit: int = 200,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    rows = list_facts(
        session,
        user_nin_hash=nin_hash,
        tax_year=tax_year,
        fact_type=fact_type,
        limit=limit,
    )
    return {"facts": [fact_to_dict(r) for r in rows]}


@router.get("/recall")
async def recall(
    q: str = Query(min_length=1, max_length=200),
    nin_hash: str | None = None,
    limit: int = 10,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    recaller = KeywordRecall(session)
    rows = recaller.recall(user_nin_hash=nin_hash, query=q, limit=limit)
    return {"facts": [fact_to_dict(r) for r in rows]}


@router.get("/anomalies")
async def anomalies(
    current_year: int,
    nin_hash: str | None = None,
    prior_year: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    findings = detect_anomalies(
        session,
        user_nin_hash=nin_hash,
        current_year=current_year,
        prior_year=prior_year,
    )
    return {"findings": [f.to_dict() for f in findings]}


@router.get("/nudges")
async def nudges(
    current_year: int,
    ytd_gross: Decimal = Query(ge=Decimal("0")),
    month: int = Query(ge=1, le=12),
    nin_hash: str | None = None,
    prior_year: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    items = suggest_nudges(
        session,
        user_nin_hash=nin_hash,
        current_year=current_year,
        ytd_gross=ytd_gross,
        month=month,
        prior_year=prior_year,
    )
    return {"nudges": [n.to_dict() for n in items]}
