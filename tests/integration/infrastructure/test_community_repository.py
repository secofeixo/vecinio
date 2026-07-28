from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.community.community import Community, DuplicateCifError
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.owner.value_objects import OwnerId
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.models import Base, CommunityModel

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


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(coefficient: str, owner_ids: tuple[OwnerId, ...] = ()) -> Unit:
    return Unit(
        id=UnitId.generate(),
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
        owner_ids=owner_ids,
    )


def make_community(cif: str = "H12345674", units: tuple[Unit, ...] = ()) -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value=cif),
        units=units,
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_all_fields(session: AsyncSession) -> None:
    owner_a, owner_b = OwnerId.generate(), OwnerId.generate()
    units = (
        make_unit("0.6", owner_ids=(owner_a, owner_b)),
        make_unit("0.4"),
    )
    community = make_community(units=units)
    repository = PostgresCommunityRepository(session)

    await repository.save(community)
    await session.commit()

    fetched = await repository.get_by_id(community.id)

    assert fetched is not None
    assert fetched.id == community.id
    assert fetched.name == community.name
    assert fetched.address == community.address
    assert fetched.cif == community.cif
    assert fetched.units == community.units


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresCommunityRepository(session)

    fetched = await repository.get_by_id(CommunityId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    unit = make_unit("1")
    community = make_community(units=(unit,))
    repository = PostgresCommunityRepository(session)

    await repository.save(community)
    await session.commit()

    community.name = "Edificio Sol Renovado"
    rebalanced_unit = Unit(
        id=unit.id,
        participation_coefficient=ParticipationCoefficient(value=Decimal("1")),
        owner_ids=(OwnerId.generate(),),
    )
    community.redefine_units([rebalanced_unit])
    await repository.save(community)
    await session.commit()

    fetched = await repository.get_by_id(community.id)
    assert fetched is not None
    assert fetched.name == "Edificio Sol Renovado"
    assert fetched.units == (rebalanced_unit,)

    count = await session.execute(
        text("SELECT count(*) FROM communities WHERE id = :id"),
        {"id": community.id.value},
    )
    assert count.scalar_one() == 1

    unit_count = await session.execute(
        text("SELECT count(*) FROM units WHERE community_id = :id"),
        {"id": community.id.value},
    )
    assert unit_count.scalar_one() == 1


@pytest.mark.asyncio
async def test_exists_by_cif_returns_true_and_false_correctly(
    session: AsyncSession,
) -> None:
    community = make_community(cif="H12345674")
    repository = PostgresCommunityRepository(session)

    await repository.save(community)
    await session.commit()

    assert await repository.exists_by_cif(CIF(value="H12345674")) is True
    assert await repository.exists_by_cif(CIF(value="A58818501")) is False


@pytest.mark.asyncio
async def test_duplicate_cif_violates_unique_constraint_at_db_level(
    session: AsyncSession,
) -> None:
    repository = PostgresCommunityRepository(session)
    await repository.save(make_community(cif="H12345674"))
    await session.commit()

    with pytest.raises(IntegrityError):
        await session.execute(
            CommunityModel.__table__.insert().values(
                id=CommunityId.generate().value,
                name="Edificio Duplicado",
                street="Calle Falsa",
                number="2",
                city="Madrid",
                postal_code="28002",
                province="Madrid",
                cif="H12345674",
            )
        )
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_save_raises_duplicate_cif_error_instead_of_integrity_error(
    session: AsyncSession,
) -> None:
    # Simulates a race that the application-level exists_by_cif check in
    # RegisterCommunity can't prevent (e.g. two concurrent registrations for
    # the same CIF racing past the check before either commits): the repository
    # itself must turn the DB-level unique violation into a domain error rather
    # than leaking a raw IntegrityError to the caller.
    repository = PostgresCommunityRepository(session)
    first = make_community(cif="H12345674")
    second = make_community(cif="H12345674")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateCifError):
        await repository.save(second)
    await session.rollback()

    count = await session.execute(
        text("SELECT count(*) FROM communities WHERE cif = :cif"),
        {"cif": "H12345674"},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_round_trips_coefficients_requiring_more_than_six_decimals(
    session: AsyncSession,
) -> None:
    # 1/3 requires far more than 6 decimal places to sum to exactly 1 across
    # three units. A NUMERIC(*, 6) column would truncate this on write and
    # make ParticipationCoefficientSumError raise on read-back, even though
    # the community was validly saved.
    a = Decimal("0.333333333333333")
    b = Decimal("0.333333333333333")
    c = Decimal("1") - a - b
    units = (make_unit(str(a)), make_unit(str(b)), make_unit(str(c)))
    community = make_community(units=units)
    repository = PostgresCommunityRepository(session)

    await repository.save(community)
    await session.commit()

    fetched = await repository.get_by_id(community.id)

    assert fetched is not None
    assert fetched.units == community.units
    total = sum(
        (unit.participation_coefficient.value for unit in fetched.units), Decimal("0")
    )
    assert total == Decimal("1")
