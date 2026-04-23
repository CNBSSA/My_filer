"""yearly_facts embedding columns (P8.10)

Revision ID: 0008_fact_embeddings
Revises: 0007_filing_tax_kind
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_fact_embeddings"
down_revision: str | None = "0007_filing_tax_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("yearly_facts") as batch:
        batch.add_column(sa.Column("embedding_json", sa.Text, nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("embedding_dim", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("yearly_facts") as batch:
        batch.drop_column("embedding_dim")
        batch.drop_column("embedding_model")
        batch.drop_column("embedding_json")
