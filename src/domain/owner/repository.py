from __future__ import annotations

from abc import ABC, abstractmethod

from .owner import Owner
from .value_objects import NIF, OwnerId


class OwnerRepository(ABC):
    @abstractmethod
    def save(self, owner: Owner) -> None: ...

    @abstractmethod
    def get_by_id(self, owner_id: OwnerId) -> Owner | None: ...

    @abstractmethod
    def exists_by_nif(self, nif: NIF) -> bool: ...
