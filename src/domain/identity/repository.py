from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.owner.value_objects import OwnerId

from .account import Account
from .refresh_token import RefreshToken
from .value_objects import AccountId, Email, RefreshTokenId


class AccountRepository(ABC):
    @abstractmethod
    async def save(self, account: Account) -> None: ...

    @abstractmethod
    async def get_by_id(self, account_id: AccountId) -> Account | None: ...

    @abstractmethod
    async def get_by_email(self, email: Email) -> Account | None: ...

    @abstractmethod
    async def exists_by_owner_id(self, owner_id: OwnerId) -> bool: ...


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def save(self, refresh_token: RefreshToken) -> None: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, refresh_token_id: RefreshTokenId) -> None: ...
