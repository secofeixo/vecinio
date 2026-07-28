from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.owner.owner import DuplicateNifError, Owner
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import NIF, Email, OwnerId, PhoneNumber

from .models import OwnerModel

_NIF_UNIQUE_CONSTRAINT = "uq_owners_nif"


class PostgresOwnerRepository(OwnerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, owner: Owner) -> None:
        stmt = pg_insert(OwnerModel).values(
            id=owner.id.value,
            nif=owner.nif.value,
            full_name=owner.full_name,
            email=owner.email.value,
            phone=owner.phone.value if owner.phone is not None else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[OwnerModel.id],
            set_={
                "nif": stmt.excluded.nif,
                "full_name": stmt.excluded.full_name,
                "email": stmt.excluded.email,
                "phone": stmt.excluded.phone,
            },
        )
        try:
            await self._session.execute(stmt)
        except IntegrityError as error:
            # Any IntegrityError leaves the underlying connection in an aborted
            # transaction, unusable until rolled back. Roll back here rather
            # than leaving it to the caller: once translated into a domain
            # exception below, nothing about that exception signals that the
            # session itself is broken.
            await self._session.rollback()
            if self._violates_nif_uniqueness(error):
                raise DuplicateNifError(
                    f"An owner with NIF {owner.nif.value} already exists"
                ) from error
            raise

    async def get_by_id(self, owner_id: OwnerId) -> Owner | None:
        stmt = select(OwnerModel).where(OwnerModel.id == owner_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def exists_by_nif(self, nif: NIF) -> bool:
        stmt = select(select(OwnerModel.id).where(OwnerModel.nif == nif.value).exists())
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    @staticmethod
    def _violates_nif_uniqueness(error: IntegrityError) -> bool:
        diag = getattr(error.orig, "diag", None)
        return getattr(diag, "constraint_name", None) == _NIF_UNIQUE_CONSTRAINT

    @staticmethod
    def _to_domain(model: OwnerModel) -> Owner:
        return Owner(
            id=OwnerId(value=model.id),
            nif=NIF(value=model.nif),
            full_name=model.full_name,
            email=Email(value=model.email),
            phone=PhoneNumber(value=model.phone) if model.phone is not None else None,
        )
