from __future__ import annotations

from src.domain.owner.owner import DuplicateNifError, Owner
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import NIF, Email, OwnerId, PhoneNumber


class RegisterOwner:
    def __init__(self, repository: OwnerRepository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        nif: str,
        full_name: str,
        email: str,
        phone: str | None,
    ) -> OwnerId:
        nif_vo = NIF(value=nif)
        if self._repository.exists_by_nif(nif_vo):
            raise DuplicateNifError(f"An owner with NIF {nif_vo.value} already exists")

        owner = Owner(
            id=OwnerId.generate(),
            nif=nif_vo,
            full_name=full_name,
            email=Email(value=email),
            phone=PhoneNumber(value=phone) if phone is not None else None,
        )

        self._repository.save(owner)
        return owner.id
