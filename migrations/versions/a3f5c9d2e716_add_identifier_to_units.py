"""add identifier to units

Revision ID: a3f5c9d2e716
Revises: 2ebb754ecf32
Create Date: 2026-07-29 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f5c9d2e716"
down_revision: str | Sequence[str] | None = "2ebb754ecf32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("units", sa.Column("identifier", sa.String(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("units", "identifier")
