from __future__ import annotations

from uuid import UUID

from src.domain.identity.account import (
    Account,
    DuplicateEmailError,
    IdentityDomainError,
)
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import OwnerId

from .security import hash_password


class OwnerNotFoundError(IdentityDomainError):
    pass


class OwnerAlreadyLinkedError(IdentityDomainError):
    pass


class RegisterAccount:
    def __init__(
        self, repository: AccountRepository, owner_repository: OwnerRepository
    ) -> None:
        self._repository = repository
        self._owner_repository = owner_repository

    async def execute(
        self,
        *,
        email: str,
        password: str,
        owner_id: UUID | None = None,
    ) -> AccountId:
        email_vo = Email(value=email)
        if await self._repository.get_by_email(email_vo) is not None:
            raise DuplicateEmailError(
                f"An account with email {email_vo.value} already exists"
            )

        owner_id_vo: OwnerId | None = None
        if owner_id is not None:
            owner_id_vo = OwnerId(value=owner_id)
            if await self._owner_repository.get_by_id(owner_id_vo) is None:
                raise OwnerNotFoundError(f"No owner found with id {owner_id}")
            if await self._repository.exists_by_owner_id(owner_id_vo):
                raise OwnerAlreadyLinkedError(
                    f"Owner {owner_id} is already linked to an account"
                )

        account = Account(
            id=AccountId.generate(),
            email=email_vo,
            password_hash=hash_password(password),
            owner_id=owner_id_vo,
        )

        await self._repository.save(account)
        return account.id
