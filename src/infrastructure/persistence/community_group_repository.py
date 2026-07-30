from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import (
    CommunityGroup,
    ConcurrentModificationError,
    DuplicateCommunityGroupSlugError,
)
from src.domain.community_group.repository import CommunityGroupRepository
from src.domain.community_group.value_objects import CommunityGroupId

from .models import CommunityGroupModel

_SLUG_UNIQUE_CONSTRAINT = "uq_community_groups_slug"


class PostgresCommunityGroupRepository(CommunityGroupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, group: CommunityGroup) -> None:
        expected_version = group.version
        new_version = expected_version + 1
        stmt = pg_insert(CommunityGroupModel).values(
            id=group.id.value,
            name=group.name,
            slug=group.slug,
            member_community_ids=[
                community_id.value for community_id in group.member_community_ids
            ],
            version=new_version,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[CommunityGroupModel.id],
            set_={
                "name": stmt.excluded.name,
                "slug": stmt.excluded.slug,
                "member_community_ids": stmt.excluded.member_community_ids,
                "version": stmt.excluded.version,
            },
            # Only takes effect on the update path (a brand-new row always
            # inserts regardless of expected_version): if another transaction
            # already advanced the version past what this aggregate was read
            # at, the WHERE fails, the update is skipped, and the statement
            # affects zero rows instead of silently overwriting the newer data.
            where=(CommunityGroupModel.version == expected_version),
        )
        # rowcount is unreliable for INSERT ... ON CONFLICT DO UPDATE ... WHERE
        # with the async psycopg driver (reports -1), so RETURNING is used to
        # detect a skipped update instead: a row comes back on insert or a
        # matched update, nothing comes back when the WHERE excludes the row.
        try:
            result = await self._session.execute(stmt.returning(CommunityGroupModel.id))
        except IntegrityError as error:
            # Any IntegrityError leaves the underlying connection in an aborted
            # transaction, unusable until rolled back. Roll back here rather
            # than leaving it to the caller: once translated into a domain
            # exception below, nothing about that exception signals that the
            # session itself is broken.
            await self._session.rollback()
            if self._violates_slug_uniqueness(error):
                raise DuplicateCommunityGroupSlugError(
                    f"A community group with slug {group.slug!r} already exists"
                ) from error
            raise

        if result.first() is None:
            raise ConcurrentModificationError(
                f"CommunityGroup {group.id.value} was modified concurrently; "
                f"expected version {expected_version}"
            )
        group.version = new_version

    async def get_by_id(self, group_id: CommunityGroupId) -> CommunityGroup | None:
        stmt = select(CommunityGroupModel).where(
            CommunityGroupModel.id == group_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    @staticmethod
    def _violates_slug_uniqueness(error: IntegrityError) -> bool:
        diag = getattr(error.orig, "diag", None)
        return getattr(diag, "constraint_name", None) == _SLUG_UNIQUE_CONSTRAINT

    @staticmethod
    def _to_domain(model: CommunityGroupModel) -> CommunityGroup:
        return CommunityGroup(
            id=CommunityGroupId(value=model.id),
            name=model.name,
            member_community_ids=tuple(
                CommunityId(value=community_id)
                for community_id in model.member_community_ids
            ),
            version=model.version,
        )
