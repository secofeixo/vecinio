from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.repository import AccountRepository, RefreshTokenRepository
from src.domain.identity.value_objects import Email, RefreshTokenId

from .security import (
    REFRESH_TOKEN_TTL,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)


class InvalidCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class Login:
    def __init__(
        self,
        account_repository: AccountRepository,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._account_repository = account_repository
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, *, email: str, password: str) -> TokenPair:
        account = await self._account_repository.get_by_email(Email(value=email))

        # Same error, same message, for "no such account" and "wrong
        # password": distinguishing them would let a caller enumerate which
        # emails are registered.
        if account is None or not verify_password(password, account.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        access_token = create_access_token(str(account.id.value))

        raw_refresh_token = generate_refresh_token()
        refresh_token = RefreshToken(
            id=RefreshTokenId.generate(),
            account_id=account.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
        )
        await self._refresh_token_repository.save(refresh_token)

        return TokenPair(access_token=access_token, refresh_token=raw_refresh_token)
