from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.application.community.assign_owner_to_unit import (
    AssignOwnerToUnit,
    CommunityNotFoundError,
    OwnerNotFoundError,
)
from src.domain.community.community import (
    Community,
    OwnerAlreadyAssignedError,
    UnitNotFoundError,
)
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.owner.owner import Owner
from src.domain.owner.value_objects import NIF, Email, OwnerId
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository

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


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(coefficient: str = "1", owner_ids: tuple[OwnerId, ...] = ()) -> Unit:
    return Unit(
        id=UnitId.generate(),
        identifier="4º-2ª",
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
        owner_ids=owner_ids,
    )


def make_community(unit: Unit, cif: str = "H12345674") -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value=cif),
        units=(unit,),
    )


def make_owner(nif: str = "12345678Z") -> Owner:
    return Owner(
        id=OwnerId.generate(),
        nif=NIF(value=nif),
        full_name="Jane Doe",
        email=Email(value="jane.doe@example.com"),
    )


async def _assert_session_usable(session: AsyncSession) -> None:
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def _count_units(session: AsyncSession, community_id: CommunityId) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM units WHERE community_id = :id"),
        {"id": community_id.value},
    )
    return result.scalar_one()


async def _unit_owner_ids(
    session: AsyncSession, community_id: CommunityId, unit_id: UnitId
) -> list:
    result = await session.execute(
        text("SELECT owner_ids FROM units WHERE community_id = :cid AND id = :uid"),
        {"cid": community_id.value, "uid": unit_id.value},
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_assigns_owner_to_unit_and_persists_updated_community(
    session: AsyncSession,
) -> None:
    unit = make_unit()
    community = make_community(unit)
    owner = make_owner()

    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    await community_repository.save(community)
    await owner_repository.save(owner)
    await session.commit()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)
    await use_case.execute(
        community_id=community.id.value,
        unit_id=unit.id.value,
        owner_id=owner.id.value,
    )
    await session.commit()

    persisted = await community_repository.get_by_id(community.id)
    assert persisted is not None
    assert persisted.units[0].owner_ids == (owner.id,)


@pytest.mark.asyncio
async def test_execute_raises_community_not_found_error_when_community_missing(
    session: AsyncSession,
) -> None:
    owner = make_owner()
    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    await owner_repository.save(owner)
    await session.commit()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            community_id=uuid4(),
            unit_id=uuid4(),
            owner_id=owner.id.value,
        )

    await _assert_session_usable(session)


@pytest.mark.asyncio
async def test_execute_raises_owner_not_found_error_when_owner_missing(
    session: AsyncSession,
) -> None:
    unit = make_unit()
    community = make_community(unit)
    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    await community_repository.save(community)
    await session.commit()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(OwnerNotFoundError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=unit.id.value,
            owner_id=uuid4(),
        )

    await _assert_session_usable(session)

    owner_ids = await _unit_owner_ids(session, community.id, unit.id)
    assert owner_ids == []


@pytest.mark.asyncio
async def test_execute_propagates_unit_not_found_error(session: AsyncSession) -> None:
    unit = make_unit()
    community = make_community(unit)
    owner = make_owner()
    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    await community_repository.save(community)
    await owner_repository.save(owner)
    await session.commit()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(UnitNotFoundError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=uuid4(),
            owner_id=owner.id.value,
        )

    await _assert_session_usable(session)

    assert await _count_units(session, community.id) == 1
    owner_ids = await _unit_owner_ids(session, community.id, unit.id)
    assert owner_ids == []


@pytest.mark.asyncio
async def test_execute_propagates_owner_already_assigned_error(
    session: AsyncSession,
) -> None:
    owner = make_owner()
    unit = make_unit(owner_ids=(owner.id,))
    community = make_community(unit)
    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    await community_repository.save(community)
    await owner_repository.save(owner)
    await session.commit()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(OwnerAlreadyAssignedError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=unit.id.value,
            owner_id=owner.id.value,
        )

    await _assert_session_usable(session)

    owner_ids = await _unit_owner_ids(session, community.id, unit.id)
    assert owner_ids == [owner.id.value]
