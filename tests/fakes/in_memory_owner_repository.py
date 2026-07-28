from __future__ import annotations

from src.domain.owner.owner import Owner
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import NIF, OwnerId


class InMemoryOwnerRepository(OwnerRepository):
    def __init__(self) -> None:
        self._owners: dict[OwnerId, Owner] = {}

    async def save(self, owner: Owner) -> None:
        self._owners[owner.id] = owner

    async def get_by_id(self, owner_id: OwnerId) -> Owner | None:
        return self._owners.get(owner_id)

    async def exists_by_nif(self, nif: NIF) -> bool:
        return any(owner.nif == nif for owner in self._owners.values())

    def all(self) -> tuple[Owner, ...]:
        return tuple(self._owners.values())
