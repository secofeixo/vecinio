from __future__ import annotations

from src.domain.community.community import Community
from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CIF, CommunityId
from src.domain.owner.value_objects import OwnerId


class InMemoryCommunityRepository(CommunityRepository):
    def __init__(self) -> None:
        self._communities: dict[CommunityId, Community] = {}

    async def save(self, community: Community) -> None:
        self._communities[community.id] = community

    async def get_by_id(self, community_id: CommunityId) -> Community | None:
        return self._communities.get(community_id)

    async def exists_by_cif(self, cif: CIF) -> bool:
        return any(community.cif == cif for community in self._communities.values())

    async def find_by_owner_id(self, owner_id: OwnerId) -> tuple[Community, ...]:
        return tuple(
            community
            for community in self._communities.values()
            if any(owner_id in unit.owner_ids for unit in community.units)
        )

    def all(self) -> tuple[Community, ...]:
        return tuple(self._communities.values())
