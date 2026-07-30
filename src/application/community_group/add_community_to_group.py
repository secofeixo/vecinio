from __future__ import annotations

from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import CommunityGroup
from src.domain.community_group.repository import CommunityGroupRepository
from src.domain.community_group.value_objects import CommunityGroupId


class CommunityGroupNotFoundError(Exception):
    pass


class CommunityNotFoundError(Exception):
    pass


class AddCommunityToGroup:
    def __init__(
        self,
        community_group_repository: CommunityGroupRepository,
        community_repository: CommunityRepository,
    ) -> None:
        self._community_group_repository = community_group_repository
        self._community_repository = community_repository

    async def execute(self, *, group_id: UUID, community_id: UUID) -> CommunityGroup:
        group_id_vo = CommunityGroupId(value=group_id)
        group = await self._community_group_repository.get_by_id(group_id_vo)
        if group is None:
            raise CommunityGroupNotFoundError(
                f"No community group found with id {group_id}"
            )

        community_id_vo = CommunityId(value=community_id)
        if await self._community_repository.get_by_id(community_id_vo) is None:
            raise CommunityNotFoundError(f"No community found with id {community_id}")

        group.add_member(community_id_vo)

        await self._community_group_repository.save(group)
        return group
