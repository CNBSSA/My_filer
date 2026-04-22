"""Aggregator selection per IDENTITY_AGGREGATOR env var (ADR-0003)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.identity.base import IdentityAggregator
from app.identity.dojah import DojahAdapter
from app.identity.prembly import PremblyAdapter
from app.identity.seamfix import SeamfixAdapter
from app.identity.service import IdentityService


def build_aggregator() -> IdentityAggregator:
    settings = get_settings()
    choice = settings.identity_aggregator.lower()
    if choice == "dojah":
        return DojahAdapter(
            api_key=settings.dojah_api_key or "dev-missing",
            app_id=settings.dojah_app_id or "dev-missing",
        )
    if choice == "seamfix":
        return SeamfixAdapter(api_key=settings.seamfix_api_key or "dev-missing")
    if choice == "prembly":
        return PremblyAdapter(api_key=settings.prembly_api_key or "dev-missing")
    raise ValueError(f"unsupported IDENTITY_AGGREGATOR: {choice}")


def build_identity_service(session: Session) -> IdentityService:
    settings = get_settings()
    return IdentityService(
        aggregator=build_aggregator(),
        session=session,
        hash_salt=settings.nin_hash_salt or "dev-salt-rotate-me",
        vault_key=settings.nin_vault_key or "dev-vault-key-rotate-me",
    )
