import jwt
import pytest

from src.application.identity.login import InvalidCredentialsError, Login
from src.application.identity.register_account import RegisterAccount
from src.application.identity.security import _jwt_secret_key
from src.domain.identity.account import Account
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_owner_repository import InMemoryOwnerRepository
from tests.fakes.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)


async def _register(account_repository: InMemoryAccountRepository) -> Account:
    account_id = await RegisterAccount(
        account_repository, InMemoryOwnerRepository()
    ).execute(email="jane.doe@example.com", password="correct-password")
    account = await account_repository.get_by_id(account_id)
    assert account is not None
    return account


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_tokens() -> None:
    account_repository = InMemoryAccountRepository()
    refresh_token_repository = InMemoryRefreshTokenRepository()
    account = await _register(account_repository)
    use_case = Login(account_repository, refresh_token_repository)

    tokens = await use_case.execute(
        email="jane.doe@example.com", password="correct-password"
    )

    assert tokens.access_token
    assert tokens.refresh_token
    payload = jwt.decode(tokens.access_token, _jwt_secret_key(), algorithms=["HS256"])
    assert payload["sub"] == str(account.id.value)


@pytest.mark.asyncio
async def test_login_persists_a_hash_of_the_refresh_token_not_the_raw_value() -> None:
    account_repository = InMemoryAccountRepository()
    refresh_token_repository = InMemoryRefreshTokenRepository()
    await _register(account_repository)
    use_case = Login(account_repository, refresh_token_repository)

    tokens = await use_case.execute(
        email="jane.doe@example.com", password="correct-password"
    )

    stored = refresh_token_repository.all()
    assert len(stored) == 1
    assert stored[0].token_hash != tokens.refresh_token


@pytest.mark.asyncio
async def test_login_with_nonexistent_email_raises_invalid_credentials_error() -> None:
    account_repository = InMemoryAccountRepository()
    refresh_token_repository = InMemoryRefreshTokenRepository()
    use_case = Login(account_repository, refresh_token_repository)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="nobody@example.com", password="whatever")


@pytest.mark.asyncio
async def test_login_with_wrong_password_raises_invalid_credentials_error() -> None:
    account_repository = InMemoryAccountRepository()
    refresh_token_repository = InMemoryRefreshTokenRepository()
    await _register(account_repository)
    use_case = Login(account_repository, refresh_token_repository)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="jane.doe@example.com", password="wrong-password")


@pytest.mark.asyncio
async def test_wrong_password_and_nonexistent_email_raise_the_identical_error() -> None:
    # Security-critical: if these messages ever diverged, a caller could probe
    # /auth/login to enumerate which emails are registered. Both branches in
    # Login.execute must raise the exact same exception type and message.
    account_repository = InMemoryAccountRepository()
    refresh_token_repository = InMemoryRefreshTokenRepository()
    await _register(account_repository)
    use_case = Login(account_repository, refresh_token_repository)

    with pytest.raises(InvalidCredentialsError) as wrong_password_error:
        await use_case.execute(email="jane.doe@example.com", password="wrong-password")

    with pytest.raises(InvalidCredentialsError) as nonexistent_email_error:
        await use_case.execute(email="nobody@example.com", password="whatever")

    assert str(wrong_password_error.value) == str(nonexistent_email_error.value)
