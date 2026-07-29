"""add version to owners

Revision ID: db29b86f1672
Revises: 02ec868ca39a
Create Date: 2026-07-29 11:06:50.928878

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db29b86f1672"
down_revision: str | Sequence[str] | None = "02ec868ca39a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "owners",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("owners", "version")
