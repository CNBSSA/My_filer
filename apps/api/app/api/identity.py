"""Identity verification endpoint (P5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


def get_service(session: Session = Depends(get_session)) -> IdentityService:
    return build_identity_service(session)


@router.post("/verify")
async def verify(
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except AggregatorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return result.to_dict()
