from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.community.community import Community
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.identity.value_objects import AccountId
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import ConcurrentModificationError, Vote
from src.domain.vote.vote_option import VoteOption
from src.domain.vote.vote_result import OptionTally, VoteResult
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.vote_repository import PostgresVoteRepository

CREATION_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def make_persisted_community(
    session: AsyncSession,
    coefficients: tuple[str, ...] = ("1",),
    cif: str = "H12345674",
) -> Community:
    units = tuple(
        Unit(
            id=UnitId.generate(),
            identifier=f"unit-{index}",
            participation_coefficient=ParticipationCoefficient(value=Decimal(value)),
        )
        for index, value in enumerate(coefficients)
    )
    community = Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=Address(
            street="Calle Mayor",
            number="1",
            city="Madrid",
            postal_code="28001",
            province="Madrid",
        ),
        cif=CIF(value=cif),
        units=units,
    )
    await PostgresCommunityRepository(session).save(community)
    await session.commit()
    return community


def make_options() -> tuple[VoteOption, ...]:
    return (
        VoteOption(id=VoteOptionId.generate(), label="Sí"),
        VoteOption(id=VoteOptionId.generate(), label="No"),
    )


def make_vote(
    community_id: CommunityId,
    options: tuple[VoteOption, ...] | None = None,
    end_date: datetime = END_DATE,
) -> Vote:
    return Vote.create(
        id=VoteId.generate(),
        community_id=community_id,
        title="¿Aprobar el presupuesto?",
        description="Votación sobre el presupuesto anual",
        options=options if options is not None else make_options(),
        end_date=end_date,
        created_by_account_id=AccountId.generate(),
        now=CREATION_NOW,
    )


def make_result(options: tuple[VoteOption, ...]) -> VoteResult:
    return VoteResult(
        tallies=tuple(
            OptionTally(
                option_id=option.id,
                unit_count=index + 1,
                weighted_coefficient=Decimal("0.123456789012345678"),
            )
            for index, option in enumerate(options)
        ),
        total_units_in_community=3,
        units_that_voted=2,
        total_participation_coefficient=Decimal("0.987654321098765432"),
        closed_at=CREATION_NOW + timedelta(days=10),
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_open_vote(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    options = make_options()
    vote = make_vote(community.id, options=options)
    repository = PostgresVoteRepository(session)

    await repository.save(vote)
    await session.commit()

    fetched = await repository.get_by_id(vote.id)

    assert fetched is not None
    assert fetched.id == vote.id
    assert fetched.community_id == vote.community_id
    assert fetched.title == vote.title
    assert fetched.description == vote.description
    assert fetched.options == options
    assert fetched.end_date == vote.end_date
    assert fetched.created_by_account_id == vote.created_by_account_id
    assert fetched.result is None
    assert fetched.version == vote.version


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_closed_vote_result(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    options = make_options()
    vote = make_vote(community.id, options=options)
    result = make_result(options)
    vote.close(result)
    repository = PostgresVoteRepository(session)

    await repository.save(vote)
    await session.commit()

    fetched = await repository.get_by_id(vote.id)

    assert fetched is not None
    assert fetched.result == result
    # Decimal precision must survive the JSONB round trip exactly, not just
    # compare equal after implicit float coercion.
    assert fetched.result is not None
    assert fetched.result.total_participation_coefficient == Decimal(
        "0.987654321098765432"
    )
    for tally in fetched.result.tallies:
        assert tally.weighted_coefficient == Decimal("0.123456789012345678")


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresVoteRepository(session)

    fetched = await repository.get_by_id(VoteId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = make_vote(community.id)
    repository = PostgresVoteRepository(session)

    await repository.save(vote)
    await session.commit()

    result = make_result(vote.options)
    vote.close(result)
    await repository.save(vote)
    await session.commit()

    fetched = await repository.get_by_id(vote.id)
    assert fetched is not None
    assert fetched.result == result


@pytest.mark.asyncio
async def test_exists_open_vote_for_community_true_then_false_after_closing(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = make_vote(community.id)
    repository = PostgresVoteRepository(session)
    await repository.save(vote)
    await session.commit()

    assert await repository.exists_open_vote_for_community(community.id) is True

    vote.close(make_result(vote.options))
    await repository.save(vote)
    await session.commit()

    assert await repository.exists_open_vote_for_community(community.id) is False


@pytest.mark.asyncio
async def test_exists_open_vote_for_community_false_for_different_community(
    session: AsyncSession,
) -> None:
    community_a = await make_persisted_community(session, cif="H12345674")
    community_b = await make_persisted_community(
        session, coefficients=("0.5", "0.5"), cif="A58818501"
    )
    repository = PostgresVoteRepository(session)
    await repository.save(make_vote(community_a.id))
    await session.commit()

    assert await repository.exists_open_vote_for_community(community_b.id) is False


@pytest.mark.asyncio
async def test_concurrent_save_raises_concurrent_modification_error(
    postgres_container: PostgresContainer, session: AsyncSession
) -> None:
    community = await make_persisted_community(session)
    vote = make_vote(community.id)
    setup_repository = PostgresVoteRepository(session)
    await setup_repository.save(vote)
    await session.commit()

    url = postgres_container.get_connection_url()
    engine_two = create_async_engine(url)
    session_factory_two = async_sessionmaker(engine_two, expire_on_commit=False)

    try:
        async with session_factory_two() as session_two:
            repository_one = PostgresVoteRepository(session)
            repository_two = PostgresVoteRepository(session_two)

            vote_one = await repository_one.get_by_id(vote.id)
            vote_two = await repository_two.get_by_id(vote.id)
            assert vote_one is not None
            assert vote_two is not None

            vote_one.close(make_result(vote_one.options))
            vote_two.close(make_result(vote_two.options))

            await repository_one.save(vote_one)
            await session.commit()

            with pytest.raises(ConcurrentModificationError):
                await repository_two.save(vote_two)
            await session_two.rollback()
    finally:
        await engine_two.dispose()
