"""filings: NRS submission receipt columns

Revision ID: 0005_filing_submission
Revises: 0004_identity_consent
Create Date: 2026-04-22
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_filing_submission"
down_revision: str | None = "0004_identity_consent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("filings") as batch:
        batch.add_column(
            sa.Column(
                "submission_status",
                sa.String(length=16),
                nullable=False,
                server_default="not_submitted",
            )
        )
        batch.add_column(sa.Column("nrs_irn", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("nrs_csid", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("nrs_qr_payload", sa.Text, nullable=True))
        batch.add_column(sa.Column("nrs_submission_error", sa.Text, nullable=True))
        batch.add_column(
            sa.Column("nrs_submitted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("filings") as batch:
        batch.drop_column("nrs_submitted_at")
        batch.drop_column("nrs_submission_error")
        batch.drop_column("nrs_qr_payload")
        batch.drop_column("nrs_csid")
        batch.drop_column("nrs_irn")
        batch.drop_column("submission_status")
