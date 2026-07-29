from datetime import datetime, timedelta, timezone

import pytest

from src.application.identity.logout import Logout
from src.application.identity.refresh_access_token import (
    InvalidRefreshTokenError,
    RefreshAccessToken,
)
from src.application.identity.security import hash_refresh_token
from src.domain.identity.refresh_token import RefreshToken
from src.domain.identity.value_objects import AccountId, RefreshTokenId
from tests.fakes.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)


def _make_refresh_token(raw_token: str) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId.generate(),
        account_id=AccountId.generate(),
        token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )


@pytest.mark.asyncio
async def test_logout_revokes_the_refresh_token() -> None:
    repository = InMemoryRefreshTokenRepository()
    await repository.save(_make_refresh_token("raw-token"))
    use_case = Logout(repository)

    await use_case.execute(refresh_token="raw-token")

    stored = await repository.get_by_token_hash(hash_refresh_token("raw-token"))
    assert stored is not None
    assert stored.revoked is True


@pytest.mark.asyncio
async def test_revoked_refresh_token_can_no_longer_be_used_to_refresh() -> None:
    repository = InMemoryRefreshTokenRepository()
    await repository.save(_make_refresh_token("raw-token"))
    logout = Logout(repository)
    refresh = RefreshAccessToken(repository)

    await logout.execute(refresh_token="raw-token")

    with pytest.raises(InvalidRefreshTokenError):
        await refresh.execute(refresh_token="raw-token")


@pytest.mark.asyncio
async def test_logout_with_unknown_refresh_token_raises_invalid_refresh_token_error() -> (
    None
):
    repository = InMemoryRefreshTokenRepository()
    use_case = Logout(repository)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(refresh_token="never-issued")
