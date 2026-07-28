from __future__ import annotations

from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CommunityId, UnitId
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import OwnerId


class CommunityNotFoundError(Exception):
    pass


class OwnerNotFoundError(Exception):
    pass


class AssignOwnerToUnit:
    def __init__(
        self,
        community_repository: CommunityRepository,
        owner_repository: OwnerRepository,
    ) -> None:
        self._community_repository = community_repository
        self._owner_repository = owner_repository

    def execute(self, *, community_id: UUID, unit_id: UUID, owner_id: UUID) -> None:
        community_id_vo = CommunityId(value=community_id)
        community = self._community_repository.get_by_id(community_id_vo)
        if community is None:
            raise CommunityNotFoundError(f"No community found with id {community_id}")

        owner_id_vo = OwnerId(value=owner_id)
        if self._owner_repository.get_by_id(owner_id_vo) is None:
            raise OwnerNotFoundError(f"No owner found with id {owner_id}")

        community.assign_owner_to_unit(UnitId(value=unit_id), owner_id_vo)

        self._community_repository.save(community)
