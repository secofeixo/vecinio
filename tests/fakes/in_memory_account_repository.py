from __future__ import annotations

from src.domain.identity.account import Account
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId, Email


class InMemoryAccountRepository(AccountRepository):
    def __init__(self) -> None:
        self._accounts: dict[AccountId, Account] = {}

    async def save(self, account: Account) -> None:
        self._accounts[account.id] = account

    async def get_by_id(self, account_id: AccountId) -> Account | None:
        return self._accounts.get(account_id)

    async def get_by_email(self, email: Email) -> Account | None:
        return next(
            (account for account in self._accounts.values() if account.email == email),
            None,
        )

    def all(self) -> tuple[Account, ...]:
        return tuple(self._accounts.values())
