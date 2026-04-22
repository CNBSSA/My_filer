"""Mai Filer ORM models — Phase 1 scope: chat threads + messages.

Further tables (users, filings, consents, documents, ...) arrive in later
phases per ROADMAP.md. Schema changes must be accompanied by an Alembic
migration under `infra/alembic/`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

MessageRole = Literal["user", "assistant", "system"]


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    thread: Mapped[Thread] = relationship("Thread", back_populates="messages")


class Document(Base):
    """Uploaded artefact (payslip, receipt, bank statement, CAC cert, ...).

    Raw content lives in object storage under `storage_key`. Structured
    extraction (if run) is stored inline as JSON for cheap read-back; the
    full audit trail lives in the audit_log table (Phase 5/6).
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("threads.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class Filing(Base):
    """A taxpayer's return in progress or finalized.

    `return_json` holds the canonical PITReturn. `audit_json` carries the
    latest Audit Shield report. When the pack is generated we stash storage
    keys for the PDF + JSON so the download endpoint can stream them.
    """

    __tablename__ = "filings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    return_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    audit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pack_json_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pack_pdf_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class ConsentLog(Base):
    """Append-only log of every identity verification attempt.

    Per `docs/COMPLIANCE.md §6`, we record actor + purpose + consent
    reference + outcome for each NIN query. Rows are never updated or
    deleted; retention follows NTAA rules (owner to confirm exact period).
    """

    __tablename__ = "consent_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("threads.id", ondelete="SET NULL"),
        nullable=True,
    )
    nin_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregator: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    consent_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    # "verified" | "rejected" | "error"
    name_match_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class IdentityRecord(Base):
    """Latest verified identity for a NIN hash.

    Raw NIN lives only as a Fernet ciphertext; the hash is the primary
    lookup key. Name fields here are whatever the aggregator returned —
    used by Audit Shield's name-match check and by Mai's conversational
    flow ("Welcome back, Chidi.") without re-calling the aggregator.
    """

    __tablename__ = "identity_records"

    nin_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    nin_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    aggregator: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    date_of_birth: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    state_of_origin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
