from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.domain.community.value_objects import CommunityId

from .quota import Quota
from .value_objects import QuotaId


class QuotaRepository(ABC):
    @abstractmethod
    async def save(self, quota: Quota) -> None: ...

    @abstractmethod
    async def get_by_id(self, quota_id: QuotaId) -> Quota | None: ...

    @abstractmethod
    async def exists_overlapping_ordinary(
        self, community_id: CommunityId, period_start: date, period_end: date
    ) -> bool: ...
