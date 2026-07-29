from __future__ import annotations

from datetime import datetime, timezone

from src.domain.identity.repository import RefreshTokenRepository

from .security import create_access_token, hash_refresh_token


class InvalidRefreshTokenError(Exception):
    pass


class RefreshAccessToken:
    # Known simplification: the refresh token itself is not rotated on use.
    # Rotation is a further hardening step for a later task, not required
    # for this first working version.
    def __init__(self, repository: RefreshTokenRepository) -> None:
        self._repository = repository

    async def execute(self, *, refresh_token: str) -> str:
        stored = await self._repository.get_by_token_hash(
            hash_refresh_token(refresh_token)
        )
        if stored is None or not stored.is_usable(now=datetime.now(timezone.utc)):
            raise InvalidRefreshTokenError(
                "Refresh token is invalid, expired, or revoked"
            )

        return create_access_token(str(stored.account_id.value))
