from __future__ import annotations

from uuid import UUID

from src.domain.identity.account import AccountAlreadyHasOwnerError
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import NIF


class AccountNotFoundError(Exception):
    pass


class OwnerNotFoundError(Exception):
    pass


class OwnerAlreadyLinkedError(Exception):
    pass


class LinkOwnerToAccount:
    def __init__(
        self, account_repository: AccountRepository, owner_repository: OwnerRepository
    ) -> None:
        self._account_repository = account_repository
        self._owner_repository = owner_repository

    async def execute(self, *, account_id: UUID, nif: str) -> None:
        account_id_vo = AccountId(value=account_id)
        account = await self._account_repository.get_by_id(account_id_vo)
        if account is None:
            raise AccountNotFoundError(f"No account found with id {account_id}")

        # Checked before any NIF lookup: cheap, and leaks nothing about
        # whether the supplied NIF exists. account.link_owner() repeats this
        # guard internally as the aggregate's own protection for any other
        # entry point -- deliberate duplication, same pattern as
        # CloseVote/Vote.close() for VoteAlreadyClosedError.
        if account.owner_id is not None:
            raise AccountAlreadyHasOwnerError(
                f"Account {account_id} already has a linked owner"
            )

        nif_vo = NIF(value=nif)
        owner = await self._owner_repository.get_by_nif(nif_vo)
        if owner is None:
            raise OwnerNotFoundError(f"No owner found with NIF {nif_vo.value}")

        if await self._account_repository.exists_by_owner_id(owner.id):
            raise OwnerAlreadyLinkedError(
                f"Owner {owner.id.value} is already linked to a different account"
            )

        account.link_owner(owner.id)
        await self._account_repository.save(account)
