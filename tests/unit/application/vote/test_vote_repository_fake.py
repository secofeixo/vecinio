from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.domain.community.value_objects import CommunityId
from src.domain.identity.value_objects import AccountId
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import Vote
from src.domain.vote.vote_option import VoteOption
from src.domain.vote.vote_result import OptionTally, VoteResult
from tests.fakes.in_memory_vote_repository import InMemoryVoteRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_options() -> tuple[VoteOption, ...]:
    return (
        VoteOption(id=VoteOptionId.generate(), label="Sí"),
        VoteOption(id=VoteOptionId.generate(), label="No"),
    )


def make_vote(community_id: CommunityId, end_date: datetime) -> Vote:
    return Vote.create(
        id=VoteId.generate(),
        community_id=community_id,
        title="Título",
        description="Descripción",
        options=make_options(),
        end_date=end_date,
        created_by_account_id=AccountId.generate(),
        now=NOW,
    )


def make_result(closed_at: datetime) -> VoteResult:
    return VoteResult(
        tallies=(
            OptionTally(
                option_id=VoteOptionId.generate(),
                unit_count=1,
                weighted_coefficient=Decimal("1"),
            ),
        ),
        total_units_in_community=1,
        units_that_voted=1,
        total_participation_coefficient=Decimal("1"),
        closed_at=closed_at,
    )


@pytest.mark.asyncio
async def test_exists_open_vote_returns_true_with_future_end_date() -> None:
    community_id = CommunityId.generate()
    vote = make_vote(community_id, end_date=NOW + timedelta(days=30))
    repository = InMemoryVoteRepository()
    await repository.save(vote)

    assert await repository.exists_open_vote_for_community(community_id) is True


@pytest.mark.asyncio
async def test_exists_open_vote_returns_true_with_past_end_date() -> None:
    community_id = CommunityId.generate()
    # Vote.create() rejects any end_date that is not strictly in the future
    # (VoteEndDateNotInFutureError), so it cannot express "the deadline has
    # already passed but nobody closed it yet" — the exact case this test
    # needs. Building the Vote via the plain pydantic constructor bypasses
    # that guard and lets us simulate a vote with a past end_date and
    # result=None, proving that "open" means result is None regardless of
    # end_date.
    vote = Vote(
        id=VoteId.generate(),
        community_id=community_id,
        title="Título",
        description="Descripción",
        options=make_options(),
        end_date=NOW - timedelta(days=1),
        created_by_account_id=AccountId.generate(),
        result=None,
    )
    repository = InMemoryVoteRepository()
    await repository.save(vote)

    assert await repository.exists_open_vote_for_community(community_id) is True


@pytest.mark.asyncio
async def test_exists_open_vote_returns_false_when_all_votes_are_closed() -> None:
    community_id = CommunityId.generate()
    vote = make_vote(community_id, end_date=NOW + timedelta(days=1))
    vote.close(make_result(closed_at=NOW + timedelta(days=2)))
    repository = InMemoryVoteRepository()
    await repository.save(vote)

    assert await repository.exists_open_vote_for_community(community_id) is False


@pytest.mark.asyncio
async def test_exists_open_vote_returns_false_when_no_votes_exist() -> None:
    community_id = CommunityId.generate()
    repository = InMemoryVoteRepository()

    assert await repository.exists_open_vote_for_community(community_id) is False


@pytest.mark.asyncio
async def test_exists_open_vote_ignores_votes_from_other_communities() -> None:
    community_id = CommunityId.generate()
    other_community_id = CommunityId.generate()
    vote = make_vote(other_community_id, end_date=NOW + timedelta(days=30))
    repository = InMemoryVoteRepository()
    await repository.save(vote)

    assert await repository.exists_open_vote_for_community(community_id) is False
