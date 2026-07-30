from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CommunityId
from src.domain.quota.allocation import allocate_largest_remainder
from src.domain.quota.quota import Quota
from src.domain.quota.quota_line import QuotaLine
from src.domain.quota.repository import QuotaRepository
from src.domain.quota.value_objects import QuotaId, QuotaType


class CommunityNotFoundError(Exception):
    pass


class OverlappingOrdinaryQuotaError(Exception):
    pass


class QuotaNotFoundError(Exception):
    pass


class CreateQuota:
    def __init__(
        self,
        quota_repository: QuotaRepository,
        community_repository: CommunityRepository,
    ) -> None:
        self._quota_repository = quota_repository
        self._community_repository = community_repository

    async def execute(
        self,
        *,
        community_id: UUID,
        type: QuotaType,
        period_start: date,
        period_end: date,
        lines: Iterable[tuple[str, Decimal]],
    ) -> QuotaId:
        community_id_vo = CommunityId(value=community_id)
        community = await self._community_repository.get_by_id(community_id_vo)
        if community is None:
            raise CommunityNotFoundError(f"No community found with id {community_id}")

        quota_lines = tuple(
            QuotaLine(concept=concept, amount=amount) for concept, amount in lines
        )
        total = sum((line.amount for line in quota_lines), Decimal("0"))

        allocations = allocate_largest_remainder(
            total,
            [
                (unit.id, unit.participation_coefficient.value)
                for unit in community.units
            ],
        )

        if type is QuotaType.ORDINARY:
            overlaps = await self._quota_repository.exists_overlapping_ordinary(
                community_id_vo, period_start, period_end
            )
            if overlaps:
                raise OverlappingOrdinaryQuotaError(
                    f"An ordinary quota already exists for community "
                    f"{community_id} overlapping {period_start}..{period_end}"
                )

        quota = Quota(
            id=QuotaId.generate(),
            community_id=community_id_vo,
            type=type,
            period_start=period_start,
            period_end=period_end,
            lines=quota_lines,
            allocations=allocations,
        )

        await self._quota_repository.save(quota)
        return quota.id
