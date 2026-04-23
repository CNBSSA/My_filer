"""cac_records table (CAC Part-A register snapshots, P9)

Revision ID: 0009_cac_records
Revises: 0008_fact_embeddings
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_cac_records"
down_revision: str | None = "0008_fact_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cac_records",
        sa.Column("rc_number", sa.String(length=64), primary_key=True),
        sa.Column("aggregator", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("registration_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("directors_json", sa.JSON, nullable=True),
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


def downgrade() -> None:
    op.drop_table("cac_records")
