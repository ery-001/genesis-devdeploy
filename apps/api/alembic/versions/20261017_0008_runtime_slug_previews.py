"""Add runtime_slug on deployment jobs for PR preview deploys.

Revision ID: 20261017_0008
Revises: 20261016_0007
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261017_0008"
down_revision = "20261016_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployment_jobs",
        sa.Column("runtime_slug", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "preview_environments",
        sa.Column("deployment_job_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_preview_environments_deployment_job_id",
        "preview_environments",
        "deployment_jobs",
        ["deployment_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_preview_environments_deployment_job_id",
        "preview_environments",
        type_="foreignkey",
    )
    op.drop_column("preview_environments", "deployment_job_id")
    op.drop_column("deployment_jobs", "runtime_slug")
