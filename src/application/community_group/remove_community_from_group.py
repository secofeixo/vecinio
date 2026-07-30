from __future__ import annotations

from uuid import UUID

from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import CommunityGroup
from src.domain.community_group.repository import CommunityGroupRepository
from src.domain.community_group.value_objects import CommunityGroupId


class CommunityGroupNotFoundError(Exception):
    pass


class RemoveCommunityFromGroup:
    def __init__(self, community_group_repository: CommunityGroupRepository) -> None:
        self._community_group_repository = community_group_repository

    async def execute(self, *, group_id: UUID, community_id: UUID) -> CommunityGroup:
        group_id_vo = CommunityGroupId(value=group_id)
        group = await self._community_group_repository.get_by_id(group_id_vo)
        if group is None:
            raise CommunityGroupNotFoundError(
                f"No community group found with id {group_id}"
            )

        group.remove_member(CommunityId(value=community_id))

        await self._community_group_repository.save(group)
        return group
