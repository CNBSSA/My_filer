"""filings.tax_kind discriminator (Phase 11)

Revision ID: 0007_filing_tax_kind
Revises: 0006_yearly_facts
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_filing_tax_kind"
down_revision: str | None = "0006_yearly_facts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("filings") as batch:
        batch.add_column(
            sa.Column(
                "tax_kind",
                sa.String(length=32),
                nullable=False,
                server_default="pit",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("filings") as batch:
        batch.drop_column("tax_kind")
