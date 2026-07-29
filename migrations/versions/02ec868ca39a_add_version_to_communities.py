"""add version to communities

Revision ID: 02ec868ca39a
Revises: 74694ff483b3
Create Date: 2026-07-29 10:51:21.651574

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02ec868ca39a"
down_revision: str | Sequence[str] | None = "74694ff483b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "communities",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("communities", "version")
