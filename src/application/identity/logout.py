from __future__ import annotations

from src.domain.identity.repository import RefreshTokenRepository

from .refresh_access_token import InvalidRefreshTokenError
from .security import hash_refresh_token


class Logout:
    def __init__(self, repository: RefreshTokenRepository) -> None:
        self._repository = repository

    async def execute(self, *, refresh_token: str) -> None:
        stored = await self._repository.get_by_token_hash(
            hash_refresh_token(refresh_token)
        )
        if stored is None:
            raise InvalidRefreshTokenError(
                "Refresh token is invalid, expired, or revoked"
            )

        await self._repository.revoke(stored.id)
