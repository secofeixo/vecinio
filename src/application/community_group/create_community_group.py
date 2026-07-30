from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import CommunityGroup
from src.domain.community_group.repository import CommunityGroupRepository
from src.domain.community_group.value_objects import CommunityGroupId


class CommunityNotFoundError(Exception):
    pass


class CreateCommunityGroup:
    def __init__(
        self,
        community_group_repository: CommunityGroupRepository,
        community_repository: CommunityRepository,
    ) -> None:
        self._community_group_repository = community_group_repository
        self._community_repository = community_repository

    async def execute(
        self, *, name: str, community_ids: Iterable[UUID]
    ) -> CommunityGroupId:
        member_community_ids = []
        for community_id in community_ids:
            member_community_ids.append(
                await self._to_existing_community_id(community_id)
            )

        group = CommunityGroup(
            id=CommunityGroupId.generate(),
            name=name,
            member_community_ids=tuple(member_community_ids),
        )

        await self._community_group_repository.save(group)
        return group.id

    async def _to_existing_community_id(self, community_id: UUID) -> CommunityId:
        community_id_vo = CommunityId(value=community_id)
        if await self._community_repository.get_by_id(community_id_vo) is None:
            raise CommunityNotFoundError(f"No community found with id {community_id}")
        return community_id_vo
