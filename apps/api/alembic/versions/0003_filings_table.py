"""filings table

Revision ID: 0003_filings
Revises: 0002_documents
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_filings"
down_revision: str | None = "0002_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "filings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("tax_year", sa.Integer, nullable=False),
        sa.Column("return_json", sa.JSON, nullable=False),
        sa.Column(
            "audit_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("audit_json", sa.JSON, nullable=True),
        sa.Column("pack_json_key", sa.String(length=255), nullable=True),
        sa.Column("pack_pdf_key", sa.String(length=255), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_filings_user_id", "filings", ["user_id"])
    op.create_index("ix_filings_tax_year", "filings", ["tax_year"])


def downgrade() -> None:
    op.drop_index("ix_filings_tax_year", table_name="filings")
    op.drop_index("ix_filings_user_id", table_name="filings")
    op.drop_table("filings")
