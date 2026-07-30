from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.community.value_objects import CommunityId, UnitId
from src.domain.quota.quota import ConcurrentModificationError, Quota
from src.domain.quota.quota_allocation import QuotaAllocation
from src.domain.quota.quota_line import QuotaLine
from src.domain.quota.repository import QuotaRepository
from src.domain.quota.value_objects import QuotaId, QuotaType

from .models import QuotaAllocationModel, QuotaLineModel, QuotaModel


class PostgresQuotaRepository(QuotaRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, quota: Quota) -> None:
        await self._upsert_quota(quota)
        await self._replace_lines(quota)
        await self._replace_allocations(quota)

    async def get_by_id(self, quota_id: QuotaId) -> Quota | None:
        stmt = (
            select(QuotaModel)
            .where(QuotaModel.id == quota_id.value)
            .options(
                selectinload(QuotaModel.lines), selectinload(QuotaModel.allocations)
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def exists_overlapping_ordinary(
        self, community_id: CommunityId, period_start: date, period_end: date
    ) -> bool:
        stmt = select(
            select(QuotaModel.id)
            .where(
                QuotaModel.community_id == community_id.value,
                QuotaModel.type == QuotaType.ORDINARY.value,
                QuotaModel.period_start <= period_end,
                QuotaModel.period_end >= period_start,
            )
            .exists()
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def _upsert_quota(self, quota: Quota) -> None:
        expected_version = quota.version
        new_version = expected_version + 1
        stmt = pg_insert(QuotaModel).values(
            id=quota.id.value,
            community_id=quota.community_id.value,
            type=quota.type.value,
            period_start=quota.period_start,
            period_end=quota.period_end,
            total=quota.total,
            supersedes_quota_id=(
                quota.supersedes_quota_id.value
                if quota.supersedes_quota_id is not None
                else None
            ),
            version=new_version,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[QuotaModel.id],
            set_={
                "community_id": stmt.excluded.community_id,
                "type": stmt.excluded.type,
                "period_start": stmt.excluded.period_start,
                "period_end": stmt.excluded.period_end,
                "total": stmt.excluded.total,
                "supersedes_quota_id": stmt.excluded.supersedes_quota_id,
                "version": stmt.excluded.version,
            },
            # Only takes effect on the update path (a brand-new row always
            # inserts regardless of expected_version): if another transaction
            # already advanced the version past what this aggregate was read
            # at, the WHERE fails, the update is skipped, and the statement
            # affects zero rows instead of silently overwriting the newer data.
            where=(QuotaModel.version == expected_version),
        )
        # rowcount is unreliable for INSERT ... ON CONFLICT DO UPDATE ... WHERE
        # with the async psycopg driver (reports -1), so RETURNING is used to
        # detect a skipped update instead: a row comes back on insert or a
        # matched update, nothing comes back when the WHERE excludes the row.
        try:
            result = await self._session.execute(stmt.returning(QuotaModel.id))
        except IntegrityError:
            # Any IntegrityError leaves the underlying connection in an
            # aborted transaction, unusable until rolled back.
            await self._session.rollback()
            raise

        if result.first() is None:
            raise ConcurrentModificationError(
                f"Quota {quota.id.value} was modified concurrently; expected "
                f"version {expected_version}"
            )
        quota.version = new_version

    async def _replace_lines(self, quota: Quota) -> None:
        await self._session.execute(
            delete(QuotaLineModel).where(QuotaLineModel.quota_id == quota.id.value)
        )
        await self._session.execute(
            pg_insert(QuotaLineModel),
            [
                {
                    "id": uuid4(),
                    "quota_id": quota.id.value,
                    "position": position,
                    "concept": line.concept,
                    "amount": line.amount,
                }
                for position, line in enumerate(quota.lines)
            ],
        )

    async def _replace_allocations(self, quota: Quota) -> None:
        await self._session.execute(
            delete(QuotaAllocationModel).where(
                QuotaAllocationModel.quota_id == quota.id.value
            )
        )
        await self._session.execute(
            pg_insert(QuotaAllocationModel),
            [
                {
                    "id": uuid4(),
                    "quota_id": quota.id.value,
                    "position": position,
                    "unit_id": allocation.unit_id.value,
                    "participation_coefficient": allocation.participation_coefficient,
                    "amount": allocation.amount,
                }
                for position, allocation in enumerate(quota.allocations)
            ],
        )

    @staticmethod
    def _to_domain(model: QuotaModel) -> Quota:
        ordered_lines = sorted(model.lines, key=lambda line: line.position)
        ordered_allocations = sorted(
            model.allocations, key=lambda allocation: allocation.position
        )
        return Quota(
            id=QuotaId(value=model.id),
            community_id=CommunityId(value=model.community_id),
            type=QuotaType(model.type),
            period_start=model.period_start,
            period_end=model.period_end,
            lines=tuple(
                QuotaLine(concept=line.concept, amount=line.amount)
                for line in ordered_lines
            ),
            allocations=tuple(
                QuotaAllocation(
                    unit_id=UnitId(value=allocation.unit_id),
                    participation_coefficient=allocation.participation_coefficient,
                    amount=allocation.amount,
                )
                for allocation in ordered_allocations
            ),
            supersedes_quota_id=(
                QuotaId(value=model.supersedes_quota_id)
                if model.supersedes_quota_id is not None
                else None
            ),
            version=model.version,
        )
