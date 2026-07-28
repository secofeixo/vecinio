from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.owner.owner import DuplicateNifError, Owner
from src.domain.owner.value_objects import NIF, Email, OwnerId, PhoneNumber
from src.infrastructure.persistence.models import Base, OwnerModel
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository

# Integration test: no Alembic migrations exist yet in this repo, so tables are
# created directly from the ORM metadata against a real, containerized Postgres.
# Once migrations are introduced, this should run them instead.


@pytest.fixture(scope="module")
def postgres_container() -> AsyncIterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        yield container


@pytest_asyncio.fixture
async def session(postgres_container: PostgresContainer) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def make_owner(nif: str = "12345678Z", has_phone: bool = True) -> Owner:
    return Owner(
        id=OwnerId.generate(),
        nif=NIF(value=nif),
        full_name="Juan Garcia",
        email=Email(value="juan.garcia@example.com"),
        phone=PhoneNumber(value="+34600123456") if has_phone else None,
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_all_fields(session: AsyncSession) -> None:
    owner = make_owner()
    repository = PostgresOwnerRepository(session)

    await repository.save(owner)
    await session.commit()

    fetched = await repository.get_by_id(owner.id)

    assert fetched == owner


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_none_phone(session: AsyncSession) -> None:
    owner = make_owner(has_phone=False)
    repository = PostgresOwnerRepository(session)

    await repository.save(owner)
    await session.commit()

    fetched = await repository.get_by_id(owner.id)

    assert fetched is not None
    assert fetched.phone is None
    assert fetched == owner


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresOwnerRepository(session)

    fetched = await repository.get_by_id(OwnerId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    owner = make_owner()
    repository = PostgresOwnerRepository(session)

    await repository.save(owner)
    await session.commit()

    owner.full_name = "Juan Garcia Renovado"
    await repository.save(owner)
    await session.commit()

    fetched = await repository.get_by_id(owner.id)
    assert fetched is not None
    assert fetched.full_name == "Juan Garcia Renovado"

    count = await session.execute(
        text("SELECT count(*) FROM owners WHERE id = :id"),
        {"id": owner.id.value},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_exists_by_nif_returns_true_and_false_correctly(
    session: AsyncSession,
) -> None:
    owner = make_owner(nif="12345678Z")
    repository = PostgresOwnerRepository(session)

    await repository.save(owner)
    await session.commit()

    assert await repository.exists_by_nif(NIF(value="12345678Z")) is True
    assert await repository.exists_by_nif(NIF(value="87654321X")) is False


@pytest.mark.asyncio
async def test_duplicate_nif_violates_unique_constraint_at_db_level(
    session: AsyncSession,
) -> None:
    repository = PostgresOwnerRepository(session)
    await repository.save(make_owner(nif="12345678Z"))
    await session.commit()

    with pytest.raises(IntegrityError):
        await session.execute(
            OwnerModel.__table__.insert().values(
                id=OwnerId.generate().value,
                nif="12345678Z",
                full_name="Otro Duplicado",
                email="otro@example.com",
                phone=None,
            )
        )
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_save_raises_duplicate_nif_error_instead_of_integrity_error(
    session: AsyncSession,
) -> None:
    # Simulates a race that the application-level exists_by_nif check in
    # RegisterOwner can't prevent (e.g. two concurrent registrations for the
    # same NIF racing past the check before either commits): the repository
    # itself must turn the DB-level unique violation into a domain error
    # rather than leaking a raw IntegrityError to the caller.
    repository = PostgresOwnerRepository(session)
    first = make_owner(nif="12345678Z")
    second = make_owner(nif="12345678Z")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateNifError):
        await repository.save(second)
    await session.rollback()

    count = await session.execute(
        text("SELECT count(*) FROM owners WHERE nif = :nif"),
        {"nif": "12345678Z"},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_session_usable_immediately_after_duplicate_nif_error(
    session: AsyncSession,
) -> None:
    # Only discovered the need for the unconditional rollback after
    # PostgresCommunityRepository was already built, so it went untested there.
    # Verify explicitly here that the session isn't left in an aborted
    # transaction state after the repository translates the IntegrityError.
    repository = PostgresOwnerRepository(session)
    first = make_owner(nif="12345678Z")
    second = make_owner(nif="12345678Z")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateNifError):
        await repository.save(second)

    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
