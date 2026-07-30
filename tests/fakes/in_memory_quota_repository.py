from __future__ import annotations

from datetime import date

from src.domain.community.value_objects import CommunityId
from src.domain.quota.quota import Quota
from src.domain.quota.repository import QuotaRepository
from src.domain.quota.value_objects import QuotaId, QuotaType


class InMemoryQuotaRepository(QuotaRepository):
    def __init__(self) -> None:
        self._quotas: dict[QuotaId, Quota] = {}

    async def save(self, quota: Quota) -> None:
        self._quotas[quota.id] = quota

    async def get_by_id(self, quota_id: QuotaId) -> Quota | None:
        return self._quotas.get(quota_id)

    async def exists_overlapping_ordinary(
        self, community_id: CommunityId, period_start: date, period_end: date
    ) -> bool:
        return any(
            quota.community_id == community_id
            and quota.type is QuotaType.ORDINARY
            and quota.period_start <= period_end
            and quota.period_end >= period_start
            for quota in self._quotas.values()
        )

    def all(self) -> tuple[Quota, ...]:
        return tuple(self._quotas.values())
