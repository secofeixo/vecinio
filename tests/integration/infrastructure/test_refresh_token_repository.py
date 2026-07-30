from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.account import Account
from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.value_objects import AccountId, Email, RefreshTokenId
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.refresh_token_repository import (
    PostgresRefreshTokenRepository,
)


async def _persist_account(session: AsyncSession) -> Account:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="argon2-hash-placeholder",
    )
    await PostgresAccountRepository(session).save(account)
    return account


def make_refresh_token(
    account_id: AccountId,
    *,
    token_hash: str = "hashed-token-value",
    revoked: bool = False,
) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId.generate(),
        account_id=account_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        revoked=revoked,
    )


@pytest.mark.asyncio
async def test_save_and_get_by_token_hash_round_trips_all_fields(
    session: AsyncSession,
) -> None:
    account = await _persist_account(session)
    refresh_token = make_refresh_token(account.id)
    repository = PostgresRefreshTokenRepository(session)

    await repository.save(refresh_token)
    await session.commit()

    fetched = await repository.get_by_token_hash(refresh_token.token_hash)

    assert fetched == refresh_token


@pytest.mark.asyncio
async def test_get_by_token_hash_returns_none_when_not_found(
    session: AsyncSession,
) -> None:
    repository = PostgresRefreshTokenRepository(session)

    fetched = await repository.get_by_token_hash("no-such-hash")

    assert fetched is None


@pytest.mark.asyncio
async def test_revoke_marks_the_token_as_revoked(session: AsyncSession) -> None:
    account = await _persist_account(session)
    refresh_token = make_refresh_token(account.id)
    repository = PostgresRefreshTokenRepository(session)
    await repository.save(refresh_token)
    await session.commit()

    await repository.revoke(refresh_token.id)
    await session.commit()

    fetched = await repository.get_by_token_hash(refresh_token.token_hash)
    assert fetched is not None
    assert fetched.revoked is True


@pytest.mark.asyncio
async def test_revoke_is_a_no_op_for_an_unknown_id(session: AsyncSession) -> None:
    repository = PostgresRefreshTokenRepository(session)

    await repository.revoke(RefreshTokenId.generate())
    await session.commit()
