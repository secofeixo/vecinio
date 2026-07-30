"""add quota bounded context

Revision ID: 7c3ca85f4754
Revises: 354471b5b8c9
Create Date: 2026-07-30 16:41:00.772743

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3ca85f4754"
down_revision: str | Sequence[str] | None = "354471b5b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "quotas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total", sa.Numeric(), nullable=False),
        sa.Column("supersedes_quota_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"], ["communities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_quota_id"], ["quotas.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quotas_community_id"), "quotas", ["community_id"], unique=False
    )
    op.create_index(
        "ix_quotas_community_type_period",
        "quotas",
        ["community_id", "type", "period_start", "period_end"],
        unique=False,
    )
    op.create_table(
        "quota_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quota_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("participation_coefficient", sa.Numeric(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["quota_id"], ["quotas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quota_id", "position", name="uq_quota_allocations_quota_position"
        ),
    )
    op.create_index(
        op.f("ix_quota_allocations_quota_id"),
        "quota_allocations",
        ["quota_id"],
        unique=False,
    )
    op.create_table(
        "quota_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quota_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("concept", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["quota_id"], ["quotas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "quota_id", "position", name="uq_quota_lines_quota_position"
        ),
    )
    op.create_index(
        op.f("ix_quota_lines_quota_id"), "quota_lines", ["quota_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_quota_lines_quota_id"), table_name="quota_lines")
    op.drop_table("quota_lines")
    op.drop_index(
        op.f("ix_quota_allocations_quota_id"), table_name="quota_allocations"
    )
    op.drop_table("quota_allocations")
    op.drop_index("ix_quotas_community_type_period", table_name="quotas")
    op.drop_index(op.f("ix_quotas_community_id"), table_name="quotas")
    op.drop_table("quotas")
