from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
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
    participation_coefficient: Mapped[str] = mapped_column(Numeric, nullable=False)
    owner_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )

    community: Mapped[CommunityModel] = relationship(back_populates="units")
