"""Deployment pipeline fields, releases, and k8s intents.

Revision ID: 20261015_0005
Revises: 20261015_0004
Create Date: 2026-10-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261015_0005"
down_revision: Union[str, Sequence[str], None] = "20261015_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deployment_jobs", sa.Column("build_logs", sa.Text(), nullable=True))
    op.add_column(
        "deployment_jobs", sa.Column("image_digest", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "deployment_jobs", sa.Column("image_tag", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "deployment_jobs", sa.Column("app_url", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "deployment_jobs",
        sa.Column(
            "simulate_failure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deployment_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("image_digest", sa.String(length=128), nullable=False),
        sa.Column("image_tag", sa.String(length=255), nullable=True),
        sa.Column("app_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["deployment_job_id"], ["deployment_jobs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_releases_project_id", "releases", ["project_id"])

    op.create_table(
        "k8s_resource_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=253), nullable=False),
        sa.Column("namespace", sa.String(length=63), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("k8s_resource_intents")
    op.drop_index("ix_releases_project_id", table_name="releases")
    op.drop_table("releases")
    op.drop_column("deployment_jobs", "simulate_failure")
    op.drop_column("deployment_jobs", "app_url")
    op.drop_column("deployment_jobs", "image_tag")
    op.drop_column("deployment_jobs", "image_digest")
    op.drop_column("deployment_jobs", "build_logs")
