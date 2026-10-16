"""Add public_url for shareable tunnel links on jobs and releases.

Revision ID: 20261016_0006
Revises: 20261015_0005
Create Date: 2026-10-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0006"
down_revision: Union[str, Sequence[str], None] = "20261015_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deployment_jobs",
        sa.Column("public_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "releases",
        sa.Column("public_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("releases", "public_url")
    op.drop_column("deployment_jobs", "public_url")
