from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.identity.account import (
    Account,
    ConcurrentModificationError,
    DuplicateEmailError,
)
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.value_objects import NIF, OwnerId
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.models import AccountModel, OwnerModel

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_alembic(command: str, target: str, url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        ["uv", "run", "alembic", command, target],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


@pytest.fixture(scope="module")
def postgres_container() -> AsyncIterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        yield container


@pytest_asyncio.fixture
async def session(postgres_container: PostgresContainer) -> AsyncIterator[AsyncSession]:
    url = postgres_container.get_connection_url()
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
    _run_alembic("downgrade", "base", url)


def make_account(
    email: str = "jane.doe@example.com", owner_id: OwnerId | None = None
) -> Account:
    return Account(
        id=AccountId.generate(),
        email=Email(value=email),
        password_hash="argon2-hash-placeholder",
        owner_id=owner_id,
    )


async def _persist_owner(session: AsyncSession, owner_id: OwnerId) -> None:
    await session.execute(
        OwnerModel.__table__.insert().values(
            id=owner_id.value,
            nif=NIF(value="12345678Z").value,
            full_name="Juan Garcia",
            email="juan.garcia@example.com",
            phone=None,
        )
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_all_fields(session: AsyncSession) -> None:
    owner_id = OwnerId.generate()
    await _persist_owner(session, owner_id)
    account = make_account(owner_id=owner_id)
    repository = PostgresAccountRepository(session)

    await repository.save(account)
    await session.commit()

    fetched = await repository.get_by_id(account.id)

    assert fetched == account


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_none_owner_id(
    session: AsyncSession,
) -> None:
    account = make_account()
    repository = PostgresAccountRepository(session)

    await repository.save(account)
    await session.commit()

    fetched = await repository.get_by_id(account.id)

    assert fetched is not None
    assert fetched.owner_id is None


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresAccountRepository(session)

    fetched = await repository.get_by_id(AccountId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_get_by_email_finds_the_account(session: AsyncSession) -> None:
    account = make_account(email="jane.doe@example.com")
    repository = PostgresAccountRepository(session)

    await repository.save(account)
    await session.commit()

    fetched = await repository.get_by_email(Email(value="jane.doe@example.com"))

    assert fetched is not None
    assert fetched.id == account.id


@pytest.mark.asyncio
async def test_get_by_email_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresAccountRepository(session)

    fetched = await repository.get_by_email(Email(value="nobody@example.com"))

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    account = make_account()
    repository = PostgresAccountRepository(session)

    await repository.save(account)
    await session.commit()

    account.password_hash = "a-new-hash"
    await repository.save(account)
    await session.commit()

    fetched = await repository.get_by_id(account.id)
    assert fetched is not None
    assert fetched.password_hash == "a-new-hash"

    count = await session.execute(
        text("SELECT count(*) FROM accounts WHERE id = :id"),
        {"id": account.id.value},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_save_raises_duplicate_email_error_instead_of_integrity_error(
    session: AsyncSession,
) -> None:
    repository = PostgresAccountRepository(session)
    first = make_account(email="jane.doe@example.com")
    second = make_account(email="jane.doe@example.com")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateEmailError):
        await repository.save(second)
    await session.rollback()

    count = await session.execute(
        text("SELECT count(*) FROM accounts WHERE email = :email"),
        {"email": "jane.doe@example.com"},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_session_usable_immediately_after_duplicate_email_error(
    session: AsyncSession,
) -> None:
    repository = PostgresAccountRepository(session)
    first = make_account(email="jane.doe@example.com")
    second = make_account(email="jane.doe@example.com")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateEmailError):
        await repository.save(second)

    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_duplicate_email_violates_unique_constraint_at_db_level(
    session: AsyncSession,
) -> None:
    repository = PostgresAccountRepository(session)
    await repository.save(make_account(email="jane.doe@example.com"))
    await session.commit()

    with pytest.raises(IntegrityError):
        await session.execute(
            AccountModel.__table__.insert().values(
                id=AccountId.generate().value,
                email="jane.doe@example.com",
                password_hash="another-hash",
                owner_id=None,
            )
        )
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_concurrent_save_raises_concurrent_modification_error(
    postgres_container: PostgresContainer, session: AsyncSession
) -> None:
    # Two processes racing to modify the same account: both read it at the
    # same version, each changes a different field, and both try to save.
    # The second save must detect the stale version instead of silently
    # clobbering the first change.
    account = make_account()
    setup_repository = PostgresAccountRepository(session)
    await setup_repository.save(account)
    await session.commit()

    url = postgres_container.get_connection_url()
    engine_two = create_async_engine(url)
    session_factory_two = async_sessionmaker(engine_two, expire_on_commit=False)

    try:
        async with session_factory_two() as session_two:
            repository_one = PostgresAccountRepository(session)
            repository_two = PostgresAccountRepository(session_two)

            account_one = await repository_one.get_by_id(account.id)
            account_two = await repository_two.get_by_id(account.id)
            assert account_one is not None
            assert account_two is not None

            account_one.password_hash = "hash-from-first-writer"
            account_two.password_hash = "hash-from-second-writer"

            await repository_one.save(account_one)
            await session.commit()

            with pytest.raises(ConcurrentModificationError):
                await repository_two.save(account_two)
            await session_two.rollback()
    finally:
        await engine_two.dispose()

    fetched = await setup_repository.get_by_id(account.id)
    assert fetched is not None
    assert fetched.password_hash == "hash-from-first-writer"
