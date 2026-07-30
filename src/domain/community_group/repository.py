from __future__ import annotations

from abc import ABC, abstractmethod

from .community_group import CommunityGroup
from .value_objects import CommunityGroupId


class CommunityGroupRepository(ABC):
    @abstractmethod
    async def save(self, group: CommunityGroup) -> None: ...

    @abstractmethod
    async def get_by_id(self, group_id: CommunityGroupId) -> CommunityGroup | None: ...
