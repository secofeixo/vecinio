from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.domain.owner.value_objects import OwnerId
from src.domain.vote.ballot import Ballot, ConcurrentBallotSubmissionError
from src.domain.vote.value_objects import BallotId, VoteId, VoteOptionId
from src.domain.vote.vote import Vote
from src.domain.vote.vote_option import VoteOption
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.models import BallotModel
from src.infrastructure.persistence.vote_repository import (
    PostgresBallotRepository,
    PostgresVoteRepository,
)

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


async def make_persisted_vote(session: AsyncSession, community_id: CommunityId) -> Vote:
    vote = Vote.create(
        id=VoteId.generate(),
        community_id=community_id,
        title="¿Aprobar el presupuesto?",
        description="Votación sobre el presupuesto anual",
        options=make_options(),
        end_date=END_DATE,
        created_by_account_id=AccountId.generate(),
        now=CREATION_NOW,
    )
    await PostgresVoteRepository(session).save(vote)
    await session.commit()
    return vote


def make_ballot(
    vote_id: VoteId,
    unit_id: UnitId,
    option_id: VoteOptionId,
    cast_by_owner_id: OwnerId | None = None,
) -> Ballot:
    return Ballot.create(
        id=BallotId.generate(),
        vote_id=vote_id,
        unit_id=unit_id,
        option_id=option_id,
        cast_by_owner_id=cast_by_owner_id or OwnerId.generate(),
        now=CREATION_NOW,
    )


@pytest.mark.asyncio
async def test_save_and_get_active_ballot_round_trips_new_ballot(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = await make_persisted_vote(session, community.id)
    unit_id = community.units[0].id
    ballot = make_ballot(vote.id, unit_id, vote.options[0].id)
    repository = PostgresBallotRepository(session)

    await repository.save(ballot)
    await session.commit()

    fetched = await repository.get_active_ballot(vote.id, unit_id)

    assert fetched is not None
    assert fetched.id == ballot.id
    assert fetched.vote_id == ballot.vote_id
    assert fetched.unit_id == ballot.unit_id
    assert fetched.option_id == ballot.option_id
    assert fetched.cast_by_owner_id == ballot.cast_by_owner_id
    assert fetched.cast_at == ballot.cast_at
    assert fetched.superseded_by_ballot_id is None


@pytest.mark.asyncio
async def test_get_active_ballot_returns_none_when_no_ballot_for_vote_unit(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = await make_persisted_vote(session, community.id)
    repository = PostgresBallotRepository(session)

    fetched = await repository.get_active_ballot(vote.id, community.units[0].id)

    assert fetched is None


@pytest.mark.asyncio
async def test_get_all_active_for_vote_returns_only_that_votes_active_ballots(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(
        session, coefficients=("0.5", "0.5"), cif="H12345674"
    )
    vote_one = await make_persisted_vote(session, community.id)
    vote_two = await make_persisted_vote(session, community.id)
    repository = PostgresBallotRepository(session)

    ballot_one = make_ballot(vote_one.id, community.units[0].id, vote_one.options[0].id)
    ballot_two = make_ballot(vote_one.id, community.units[1].id, vote_one.options[1].id)
    ballot_other_vote = make_ballot(
        vote_two.id, community.units[0].id, vote_two.options[0].id
    )
    await repository.save(ballot_one)
    await repository.save(ballot_two)
    await repository.save(ballot_other_vote)
    await session.commit()

    active = await repository.get_all_active_for_vote(vote_one.id)

    assert {ballot.id for ballot in active} == {ballot_one.id, ballot_two.id}


@pytest.mark.asyncio
async def test_supersede_makes_new_ballot_active_and_keeps_old_one_persisted(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = await make_persisted_vote(session, community.id)
    unit_id = community.units[0].id
    repository = PostgresBallotRepository(session)

    old_ballot = make_ballot(vote.id, unit_id, vote.options[0].id)
    await repository.save(old_ballot)
    await session.commit()

    new_ballot = make_ballot(
        vote.id,
        unit_id,
        vote.options[1].id,
        cast_by_owner_id=old_ballot.cast_by_owner_id,
    )
    old_ballot.supersede(new_ballot.id)
    await repository.save(old_ballot)
    await repository.save(new_ballot)
    await session.commit()

    active = await repository.get_active_ballot(vote.id, unit_id)
    assert active is not None
    assert active.id == new_ballot.id

    # The superseded ballot must still exist in the database, not be deleted.
    stmt_result = await session.execute(
        select(BallotModel).where(BallotModel.id == old_ballot.id.value)
    )
    old_row = stmt_result.scalar_one()
    assert old_row.superseded_by_ballot_id == new_ballot.id.value


@pytest.mark.asyncio
async def test_two_simultaneous_active_ballots_for_same_vote_and_unit_raise_error(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    vote = await make_persisted_vote(session, community.id)
    unit_id = community.units[0].id
    repository = PostgresBallotRepository(session)

    first = make_ballot(vote.id, unit_id, vote.options[0].id)
    await repository.save(first)
    await session.commit()

    second = make_ballot(vote.id, unit_id, vote.options[1].id)

    with pytest.raises(ConcurrentBallotSubmissionError):
        await repository.save(second)


@pytest.mark.asyncio
async def test_second_ballot_with_superseded_pointer_does_not_violate_partial_index(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(
        session, coefficients=("0.5", "0.5"), cif="H12345674"
    )
    vote = await make_persisted_vote(session, community.id)
    unit_id = community.units[0].id
    repository = PostgresBallotRepository(session)

    active_ballot = make_ballot(vote.id, unit_id, vote.options[0].id)
    await repository.save(active_ballot)
    await session.commit()

    # A third, unrelated ballot (different unit) that the FK on
    # superseded_by_ballot_id can validly point to.
    third_ballot = make_ballot(vote.id, community.units[1].id, vote.options[0].id)
    await repository.save(third_ballot)
    await session.commit()

    superseded_ballot = Ballot(
        id=BallotId.generate(),
        vote_id=vote.id,
        unit_id=unit_id,
        option_id=vote.options[1].id,
        cast_by_owner_id=OwnerId.generate(),
        cast_at=CREATION_NOW,
        superseded_by_ballot_id=third_ballot.id,
    )

    # Must not raise: the partial index only constrains rows where
    # superseded_by_ballot_id IS NULL, so a second (vote_id, unit_id) row that
    # is already marked superseded is not a duplicate active ballot.
    await repository.save(superseded_ballot)
    await session.commit()

    fetched_active = await repository.get_active_ballot(vote.id, unit_id)
    assert fetched_active is not None
    assert fetched_active.id == active_ballot.id
