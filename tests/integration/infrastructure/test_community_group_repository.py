from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import (
    CommunityGroup,
    ConcurrentModificationError,
    DuplicateCommunityGroupSlugError,
)
from src.domain.community_group.value_objects import CommunityGroupId
from src.infrastructure.persistence.community_group_repository import (
    PostgresCommunityGroupRepository,
)
from src.infrastructure.persistence.models import CommunityGroupModel


def make_group(name: str = "206-208") -> CommunityGroup:
    return CommunityGroup(
        id=CommunityGroupId.generate(),
        name=name,
        member_community_ids=(CommunityId.generate(), CommunityId.generate()),
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_all_fields(session: AsyncSession) -> None:
    group = make_group()
    repository = PostgresCommunityGroupRepository(session)

    await repository.save(group)
    await session.commit()

    fetched = await repository.get_by_id(group.id)

    assert fetched is not None
    assert fetched.id == group.id
    assert fetched.name == group.name
    assert fetched.slug == group.slug
    assert fetched.member_community_ids == group.member_community_ids


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresCommunityGroupRepository(session)

    fetched = await repository.get_by_id(CommunityGroupId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    group = make_group()
    repository = PostgresCommunityGroupRepository(session)

    await repository.save(group)
    await session.commit()

    new_member = CommunityId.generate()
    group.add_member(new_member)
    await repository.save(group)
    await session.commit()

    fetched = await repository.get_by_id(group.id)
    assert fetched is not None
    assert new_member in fetched.member_community_ids

    count = await session.execute(
        text("SELECT count(*) FROM community_groups WHERE id = :id"),
        {"id": group.id.value},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_duplicate_slug_violates_unique_constraint_at_db_level(
    session: AsyncSession,
) -> None:
    repository = PostgresCommunityGroupRepository(session)
    group = make_group(name="206-208")
    await repository.save(group)
    await session.commit()

    with pytest.raises(IntegrityError):
        await session.execute(
            CommunityGroupModel.__table__.insert().values(
                id=CommunityGroupId.generate().value,
                name="206-208 duplicado",
                slug="206-208",
                member_community_ids=[],
                version=1,
            )
        )
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_save_raises_duplicate_slug_error_instead_of_integrity_error(
    session: AsyncSession,
) -> None:
    # Two different names that normalize to the same slug — there's no
    # application-level pre-check for slugs, so the repository is the only
    # place this race can be caught.
    repository = PostgresCommunityGroupRepository(session)
    first = make_group(name="Jardín")
    second = make_group(name="jardin")

    await repository.save(first)
    await session.commit()

    with pytest.raises(DuplicateCommunityGroupSlugError):
        await repository.save(second)
    await session.rollback()

    count = await session.execute(
        text("SELECT count(*) FROM community_groups WHERE slug = :slug"),
        {"slug": "jardin"},
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_concurrent_save_raises_concurrent_modification_error(
    postgres_container: PostgresContainer, session: AsyncSession
) -> None:
    # Simulates two processes racing to modify the same group: both read it at
    # the same version, each independently adds a different community, and
    # both try to save. The second save must detect the stale version instead
    # of silently clobbering the first addition.
    group = make_group()
    setup_repository = PostgresCommunityGroupRepository(session)
    await setup_repository.save(group)
    await session.commit()

    url = postgres_container.get_connection_url()
    engine_two = create_async_engine(url)
    session_factory_two = async_sessionmaker(engine_two, expire_on_commit=False)

    try:
        async with session_factory_two() as session_two:
            repository_one = PostgresCommunityGroupRepository(session)
            repository_two = PostgresCommunityGroupRepository(session_two)

            group_one = await repository_one.get_by_id(group.id)
            group_two = await repository_two.get_by_id(group.id)
            assert group_one is not None
            assert group_two is not None

            community_a = CommunityId.generate()
            community_b = CommunityId.generate()
            group_one.add_member(community_a)
            group_two.add_member(community_b)

            await repository_one.save(group_one)
            await session.commit()

            with pytest.raises(ConcurrentModificationError):
                await repository_two.save(group_two)
            await session_two.rollback()
    finally:
        await engine_two.dispose()

    fetched = await setup_repository.get_by_id(group.id)
    assert fetched is not None
    assert community_a in fetched.member_community_ids
    assert community_b not in fetched.member_community_ids
