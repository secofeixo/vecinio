from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.application.identity.refresh_access_token import (
    InvalidRefreshTokenError,
    RefreshAccessToken,
)
from src.application.identity.security import _jwt_secret_key, hash_refresh_token
from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.value_objects import AccountId, RefreshTokenId
from tests.fakes.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)


def _make_refresh_token(
    *,
    raw_token: str,
    account_id: AccountId,
    revoked: bool = False,
    ttl_minutes: int = 60,
) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId.generate(),
        account_id=account_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        revoked=revoked,
    )


@pytest.mark.asyncio
async def test_valid_refresh_token_issues_a_new_access_token() -> None:
    repository = InMemoryRefreshTokenRepository()
    account_id = AccountId.generate()
    await repository.save(
        _make_refresh_token(raw_token="raw-token", account_id=account_id)
    )
    use_case = RefreshAccessToken(repository)

    access_token = await use_case.execute(refresh_token="raw-token")

    payload = jwt.decode(access_token, _jwt_secret_key(), algorithms=["HS256"])
    assert payload["sub"] == str(account_id.value)


@pytest.mark.asyncio
async def test_unknown_refresh_token_raises_invalid_refresh_token_error() -> None:
    repository = InMemoryRefreshTokenRepository()
    use_case = RefreshAccessToken(repository)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(refresh_token="never-issued")


@pytest.mark.asyncio
async def test_revoked_refresh_token_raises_invalid_refresh_token_error() -> None:
    repository = InMemoryRefreshTokenRepository()
    await repository.save(
        _make_refresh_token(
            raw_token="raw-token", account_id=AccountId.generate(), revoked=True
        )
    )
    use_case = RefreshAccessToken(repository)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(refresh_token="raw-token")


@pytest.mark.asyncio
async def test_expired_refresh_token_raises_invalid_refresh_token_error() -> None:
    repository = InMemoryRefreshTokenRepository()
    await repository.save(
        _make_refresh_token(
            raw_token="raw-token",
            account_id=AccountId.generate(),
            ttl_minutes=-1,
        )
    )
    use_case = RefreshAccessToken(repository)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(refresh_token="raw-token")
