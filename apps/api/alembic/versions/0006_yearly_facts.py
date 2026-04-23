"""yearly_facts table (Phase 8 Learning Partner)

Revision ID: 0006_yearly_facts
Revises: 0005_filing_submission
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_yearly_facts"
down_revision: str | None = "0005_filing_submission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "yearly_facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_nin_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "filing_id",
            sa.String(length=36),
            sa.ForeignKey("filings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column("fact_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column(
            "value_kind", sa.String(length=16), nullable=False, server_default="decimal"
        ),
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="NGN"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="filing"),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("meta_json", sa.JSON, nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_yearly_facts_nin_hash", "yearly_facts", ["user_nin_hash"])
    op.create_index("ix_yearly_facts_tax_year", "yearly_facts", ["tax_year"])
    op.create_index("ix_yearly_facts_fact_type", "yearly_facts", ["fact_type"])


def downgrade() -> None:
    op.drop_index("ix_yearly_facts_fact_type", table_name="yearly_facts")
    op.drop_index("ix_yearly_facts_tax_year", table_name="yearly_facts")
    op.drop_index("ix_yearly_facts_nin_hash", table_name="yearly_facts")
    op.drop_table("yearly_facts")
