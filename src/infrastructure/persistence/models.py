from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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
