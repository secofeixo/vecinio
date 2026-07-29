from __future__ import annotations

from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.repository import RefreshTokenRepository
from src.domain.identity.value_objects import RefreshTokenId


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self._tokens: dict[RefreshTokenId, RefreshToken] = {}

    async def save(self, refresh_token: RefreshToken) -> None:
        self._tokens[refresh_token.id] = refresh_token

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return next(
            (
                token
                for token in self._tokens.values()
                if token.token_hash == token_hash
            ),
            None,
        )

    async def revoke(self, refresh_token_id: RefreshTokenId) -> None:
        token = self._tokens.get(refresh_token_id)
        if token is not None:
            token.revoked = True

    def all(self) -> tuple[RefreshToken, ...]:
        return tuple(self._tokens.values())
