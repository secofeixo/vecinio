"""accounts owner_id ondelete set null

Revision ID: 2ebb754ecf32
Revises: 2c31e6ec57d1
Create Date: 2026-07-29 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2ebb754ecf32"
down_revision: str | Sequence[str] | None = "2c31e6ec57d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "accounts_owner_id_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    # owner_id is a nullable, optional link (an Account does not require an
    # Owner). Deleting the referenced Owner should detach the link, not block
    # the deletion (default NO ACTION/RESTRICT) and not cascade-delete the
    # Account (a person can stop being a property owner without losing their
    # login).
    op.drop_constraint(_FK_NAME, "accounts", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME, "accounts", "owners", ["owner_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_FK_NAME, "accounts", type_="foreignkey")
    op.create_foreign_key(_FK_NAME, "accounts", "owners", ["owner_id"], ["id"])
