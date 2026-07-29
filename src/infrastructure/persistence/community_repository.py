from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.community.community import (
    Community,
    ConcurrentModificationError,
    DuplicateCifError,
)
from src.domain.community.repository import CommunityRepository
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.owner.value_objects import OwnerId

from .models import CommunityModel, UnitModel

_CIF_UNIQUE_CONSTRAINT = "uq_communities_cif"


class PostgresCommunityRepository(CommunityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, community: Community) -> None:
        await self._upsert_community(community)
        await self._replace_units(community)

    async def get_by_id(self, community_id: CommunityId) -> Community | None:
        stmt = (
            select(CommunityModel)
            .where(CommunityModel.id == community_id.value)
            .options(selectinload(CommunityModel.units))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def exists_by_cif(self, cif: CIF) -> bool:
        stmt = select(
            select(CommunityModel.id).where(CommunityModel.cif == cif.value).exists()
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def _upsert_community(self, community: Community) -> None:
        expected_version = community.version
        new_version = expected_version + 1
        stmt = pg_insert(CommunityModel).values(
            id=community.id.value,
            name=community.name,
            street=community.address.street,
            number=community.address.number,
            city=community.address.city,
            postal_code=community.address.postal_code,
            province=community.address.province,
            cif=community.cif.value,
            version=new_version,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CommunityModel.id],
            set_={
                "name": stmt.excluded.name,
                "street": stmt.excluded.street,
                "number": stmt.excluded.number,
                "city": stmt.excluded.city,
                "postal_code": stmt.excluded.postal_code,
                "province": stmt.excluded.province,
                "cif": stmt.excluded.cif,
                "version": stmt.excluded.version,
            },
            # Only takes effect on the update path (a brand-new row always
            # inserts regardless of expected_version): if another transaction
            # already advanced the version past what this aggregate was read
            # at, the WHERE fails, the update is skipped, and the statement
            # affects zero rows instead of silently overwriting the newer data.
            where=(CommunityModel.version == expected_version),
        )
        # rowcount is unreliable for INSERT ... ON CONFLICT DO UPDATE ... WHERE
        # with the async psycopg driver (reports -1), so RETURNING is used to
        # detect a skipped update instead: a row comes back on insert or a
        # matched update, nothing comes back when the WHERE excludes the row.
        try:
            result = await self._session.execute(stmt.returning(CommunityModel.id))
        except IntegrityError as error:
            # Any IntegrityError leaves the underlying connection in an aborted
            # transaction, unusable until rolled back. Roll back here rather
            # than leaving it to the caller: once translated into a domain
            # exception below, nothing about that exception signals that the
            # session itself is broken.
            await self._session.rollback()
            if self._violates_cif_uniqueness(error):
                raise DuplicateCifError(
                    f"A community with CIF {community.cif.value} already exists"
                ) from error
            raise

        if result.first() is None:
            raise ConcurrentModificationError(
                f"Community {community.id.value} was modified concurrently; "
                f"expected version {expected_version}"
            )
        community.version = new_version

    @staticmethod
    def _violates_cif_uniqueness(error: IntegrityError) -> bool:
        diag = getattr(error.orig, "diag", None)
        return getattr(diag, "constraint_name", None) == _CIF_UNIQUE_CONSTRAINT

    async def _replace_units(self, community: Community) -> None:
        await self._session.execute(
            delete(UnitModel).where(UnitModel.community_id == community.id.value)
        )
        if not community.units:
            return

        await self._session.execute(
            pg_insert(UnitModel),
            [
                {
                    "id": unit.id.value,
                    "community_id": community.id.value,
                    "position": position,
                    "participation_coefficient": unit.participation_coefficient.value,
                    "owner_ids": [owner_id.value for owner_id in unit.owner_ids],
                }
                for position, unit in enumerate(community.units)
            ],
        )

    @staticmethod
    def _to_domain(model: CommunityModel) -> Community:
        ordered_units = sorted(model.units, key=lambda unit: unit.position)
        return Community(
            id=CommunityId(value=model.id),
            name=model.name,
            address=Address(
                street=model.street,
                number=model.number,
                city=model.city,
                postal_code=model.postal_code,
                province=model.province,
            ),
            cif=CIF(value=model.cif),
            version=model.version,
            units=tuple(
                Unit(
                    id=UnitId(value=unit.id),
                    participation_coefficient=ParticipationCoefficient(
                        value=unit.participation_coefficient
                    ),
                    owner_ids=tuple(
                        OwnerId(value=owner_id) for owner_id in unit.owner_ids
                    ),
                )
                for unit in ordered_units
            ),
        )
