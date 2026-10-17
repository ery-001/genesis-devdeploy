"""Store GitHub check_run id on preview environments.

Revision ID: 20261017_0009
Revises: 20261017_0008
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261017_0009"
down_revision = "20261017_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "preview_environments",
        sa.Column("github_check_run_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("preview_environments", "github_check_run_id")
