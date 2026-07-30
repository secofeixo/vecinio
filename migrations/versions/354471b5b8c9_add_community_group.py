"""add community_group

Revision ID: 354471b5b8c9
Revises: a3f5c9d2e716
Create Date: 2026-07-29 19:45:02.556430

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "354471b5b8c9"
down_revision: str | Sequence[str] | None = "a3f5c9d2e716"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "community_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("member_community_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_community_groups_slug"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("community_groups")
