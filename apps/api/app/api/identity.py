"""Identity verification endpoint (P5)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.limits import limiter

log = logging.getLogger(__name__)

from app.db.session import get_session
from app.identity.base import AggregatorError
from app.identity.factory import build_identity_service
from app.identity.service import ConsentRequiredError, IdentityService

router = APIRouter(prefix="/v1/identity", tags=["identity"])


class VerifyRequest(BaseModel):
    nin: str = Field(min_length=11, max_length=11, pattern=r"^\d{11}$")
    consent: bool = Field(
        default=False,
        description=(
            "MUST be True. Per NDPR / NDPC, a NIN query cannot proceed without "
            "explicit taxpayer consent."
        ),
    )
    declared_name: str | None = Field(default=None, max_length=200)
    purpose: str = Field(default="tax_filing", max_length=128)
    thread_id: str | None = None


class VerifyCACRequest(BaseModel):
    rc_number: str = Field(min_length=1, max_length=64)
    consent: bool = Field(
        default=False,
        description=(
            "MUST be True. A CAC register query is a data-subject action under "
            "NDPR and requires explicit consent from an authorized officer."
        ),
    )
    declared_name: str | None = Field(default=None, max_length=200)
    purpose: str = Field(default="corporate_filing", max_length=128)
    thread_id: str | None = None


def get_service(session: Session = Depends(get_session)) -> IdentityService:
    return build_identity_service(session)


@router.post("/verify")
@limiter.limit("10/minute")
async def verify(
    request: Request,
    body: VerifyRequest,
    service: IdentityService = Depends(get_service),
) -> dict[str, Any]:
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent must be explicitly granted (consent=true).",
        )
    try:
        result = service.verify_taxpayer(
            nin=body.nin,
            consent=body.consent,
            declared_name=body.declared_name,
            purpose=body.purpose,
            thread_id=body.thread_id,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        log.warning("Identity verify validation error", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid identity data supplied. Check the request and try again.",
        ) from exc
    except AggregatorError as exc:
        log.error("Identity aggregator error", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Identity verification is temporarily unavailable. Please try again.",
        ) from exc
    return result.to_dict()


@router.post("/verify-cac")
@limiter.limit("10/minute")
async def verify_cac(
    request: Request,
    body: VerifyCACRequest,
    service: IdentityService = Depends(get_service),
) -> dict[str, Any]:
    """Verify a CAC RC number against the Part-A register (P9)."""
    if not body.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent must be explicitly granted (consent=true).",
        )
    try:
        result = service.verify_organization(
            rc_number=body.rc_number,
            consent=body.consent,
            declared_name=body.declared_name,
            purpose=body.purpose,
            thread_id=body.thread_id,
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        log.warning("CAC verify validation error", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid corporate data supplied. Check the request and try again.",
        ) from exc
    except AggregatorError as exc:
        log.error("CAC aggregator error", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Corporate registry verification is temporarily unavailable. Please try again.",
        ) from exc
    return result.to_dict()
