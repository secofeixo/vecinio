from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.repository import RefreshTokenRepository
from src.domain.identity.value_objects import AccountId, RefreshTokenId

from .models import RefreshTokenModel


class PostgresRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, refresh_token: RefreshToken) -> None:
        stmt = pg_insert(RefreshTokenModel).values(
            id=refresh_token.id.value,
            account_id=refresh_token.account_id.value,
            token_hash=refresh_token.token_hash,
            expires_at=refresh_token.expires_at,
            revoked=refresh_token.revoked,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RefreshTokenModel.id],
            set_={
                "token_hash": stmt.excluded.token_hash,
                "expires_at": stmt.excluded.expires_at,
                "revoked": stmt.excluded.revoked,
            },
        )
        await self._session.execute(stmt)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def revoke(self, refresh_token_id: RefreshTokenId) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == refresh_token_id.value)
            .values(revoked=True)
        )
        await self._session.execute(stmt)

    @staticmethod
    def _to_domain(model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=RefreshTokenId(value=model.id),
            account_id=AccountId(value=model.account_id),
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            revoked=model.revoked,
        )
