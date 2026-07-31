from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CommunityModel(Base):
    __tablename__ = "communities"
    __table_args__ = (UniqueConstraint("cif", name="uq_communities_cif"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    street: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    postal_code: Mapped[str] = mapped_column(String, nullable=False)
    province: Mapped[str] = mapped_column(String, nullable=False)
    cif: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    units: Mapped[list[UnitModel]] = relationship(
        back_populates="community", cascade="all, delete-orphan"
    )


class UnitModel(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint(
            "community_id", "position", name="uq_units_community_position"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Persists the unit's index within Community.units — the domain treats that
    # tuple as ordered (equality and redefine_units depend on it), and the
    # repository replaces all units on every save, so row insertion order alone
    # can't be relied on to survive a read-back.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    participation_coefficient: Mapped[str] = mapped_column(Numeric, nullable=False)
    owner_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )

    community: Mapped[CommunityModel] = relationship(back_populates="units")


class OwnerModel(Base):
    __tablename__ = "owners"
    __table_args__ = (UniqueConstraint("nif", name="uq_owners_nif"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nif: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_accounts_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("owners.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CommunityGroupModel(Base):
    __tablename__ = "community_groups"
    __table_args__ = (UniqueConstraint("slug", name="uq_community_groups_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    member_community_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class QuotaModel(Base):
    __tablename__ = "quotas"
    __table_args__ = (
        Index(
            "ix_quotas_community_type_period",
            "community_id",
            "type",
            "period_start",
            "period_end",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[str] = mapped_column(Numeric, nullable=False)
    supersedes_quota_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotas.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    lines: Mapped[list[QuotaLineModel]] = relationship(
        back_populates="quota", cascade="all, delete-orphan"
    )
    allocations: Mapped[list[QuotaAllocationModel]] = relationship(
        back_populates="quota", cascade="all, delete-orphan"
    )


class QuotaLineModel(Base):
    __tablename__ = "quota_lines"
    __table_args__ = (
        UniqueConstraint("quota_id", "position", name="uq_quota_lines_quota_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    quota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quotas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    concept: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(Numeric, nullable=False)

    quota: Mapped[QuotaModel] = relationship(back_populates="lines")


class QuotaAllocationModel(Base):
    __tablename__ = "quota_allocations"
    __table_args__ = (
        UniqueConstraint(
            "quota_id", "position", name="uq_quota_allocations_quota_position"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    quota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quotas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    participation_coefficient: Mapped[str] = mapped_column(Numeric, nullable=False)
    amount: Mapped[str] = mapped_column(Numeric, nullable=False)

    quota: Mapped[QuotaModel] = relationship(back_populates="allocations")


class VoteModel(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    # none_as_null=True: without it, SQLAlchemy's JSON/JSONB bind processor
    # writes a Python None as the JSON literal `null` rather than SQL NULL,
    # which would silently break `result IS NULL` queries such as
    # exists_open_vote_for_community.
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class BallotModel(Base):
    __tablename__ = "ballots"
    __table_args__ = (
        # Enforces "at most one active ballot per (vote_id, unit_id)" at the DB
        # level — partial so a unit can accumulate any number of superseded
        # (historical) ballots without ever colliding, only the single row
        # with superseded_by_ballot_id IS NULL per (vote_id, unit_id) is
        # constrained.
        Index(
            "ix_ballots_active_per_vote_unit",
            "vote_id",
            "unit_id",
            unique=True,
            postgresql_where=text("superseded_by_ballot_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("votes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # No FK to units.id: PostgresCommunityRepository._replace_units deletes and
    # reinserts every Unit row of a Community on every save, so a
    # ON DELETE CASCADE FK here would cascade-delete ballot history on
    # unrelated community edits. Same reasoning as QuotaAllocationModel.unit_id
    # above. Membership of unit_id in the vote's Community is validated by
    # CastBallot/CloseVote in the application layer.
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # No FK to votes' embedded options: options live in VoteModel.options
    # (JSONB), not a relational table.
    option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cast_by_owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    cast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # No special ondelete: a superseding ballot being deleted must not cascade
    # into deleting the ballot it superseded — the superseded row is history
    # and outlives the pointer to it. Deleting a referenced row directly
    # would violate this FK, which is the desired behavior (ballots are never
    # deleted in normal operation).
    # deferrable/initially="DEFERRED": CastBallot's real save order is
    # save(old_ballot) [UPDATE, sets this column to new_ballot.id] then
    # save(new_ballot) [INSERT] — at the moment the UPDATE runs, new_ballot's
    # row doesn't exist yet. An immediate FK check would reject that UPDATE.
    # Deferring the check to COMMIT lets both statements land in the same
    # transaction before the reference is validated. This also doesn't
    # reopen the partial-unique-index race: old_ballot stops being "active"
    # (superseded_by_ballot_id no longer NULL) the instant its UPDATE runs,
    # before new_ballot's INSERT is even issued.
    superseded_by_ballot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ballots.id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
