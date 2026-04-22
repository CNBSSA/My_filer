"""identity_records + consent_log tables

Revision ID: 0004_identity_consent
Revises: 0003_filings
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_identity_consent"
down_revision: str | None = "0003_filings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_records",
        sa.Column("nin_hash", sa.String(length=64), primary_key=True),
        sa.Column("nin_ciphertext", sa.Text, nullable=False),
        sa.Column("aggregator", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("middle_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("state_of_origin", sa.String(length=64), nullable=True),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "consent_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column(
            "thread_id",
            sa.String(length=36),
            sa.ForeignKey("threads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nin_hash", sa.String(length=64), nullable=False),
        sa.Column("aggregator", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=128), nullable=False),
        sa.Column(
            "consent_granted", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("name_match_status", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_consent_log_user_id", "consent_log", ["user_id"])
    op.create_index("ix_consent_log_nin_hash", "consent_log", ["nin_hash"])


def downgrade() -> None:
    op.drop_index("ix_consent_log_nin_hash", table_name="consent_log")
    op.drop_index("ix_consent_log_user_id", table_name="consent_log")
    op.drop_table("consent_log")
    op.drop_table("identity_records")
