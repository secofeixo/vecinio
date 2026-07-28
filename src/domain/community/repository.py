from __future__ import annotations

from abc import ABC, abstractmethod

from .community import Community
from .value_objects import CIF, CommunityId


class CommunityRepository(ABC):
    @abstractmethod
    async def save(self, community: Community) -> None: ...

    @abstractmethod
    async def get_by_id(self, community_id: CommunityId) -> Community | None: ...

    @abstractmethod
    async def exists_by_cif(self, cif: CIF) -> bool: ...
