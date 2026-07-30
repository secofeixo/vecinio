from __future__ import annotations

from src.domain.community_group.community_group import CommunityGroup
from src.domain.community_group.repository import CommunityGroupRepository
from src.domain.community_group.value_objects import CommunityGroupId


class InMemoryCommunityGroupRepository(CommunityGroupRepository):
    def __init__(self) -> None:
        self._groups: dict[CommunityGroupId, CommunityGroup] = {}

    async def save(self, group: CommunityGroup) -> None:
        self._groups[group.id] = group

    async def get_by_id(self, group_id: CommunityGroupId) -> CommunityGroup | None:
        return self._groups.get(group_id)

    def all(self) -> tuple[CommunityGroup, ...]:
        return tuple(self._groups.values())
