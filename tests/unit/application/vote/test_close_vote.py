from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.vote.close_vote import (
    AccountNotAuthorizedToCloseVoteError,
    AccountNotFoundError,
    CloseVote,
    CommunityNotFoundError,
    VoteHasNotEndedYetError,
    VoteNotFoundError,
)
from src.domain.community.community import Community
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.identity.account import Account
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.value_objects import OwnerId
from src.domain.vote.ballot import Ballot
from src.domain.vote.value_objects import BallotId, VoteId, VoteOptionId
from src.domain.vote.vote import Vote, VoteAlreadyClosedError
from src.domain.vote.vote_option import VoteOption
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_ballot_repository import InMemoryBallotRepository
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository
from tests.fakes.in_memory_vote_repository import InMemoryVoteRepository

CREATION_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
AFTER_END_DATE = datetime(2026, 1, 2, tzinfo=timezone.utc)
BEFORE_END_DATE = datetime(2025, 12, 31, tzinfo=timezone.utc)


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(owner_ids: tuple[OwnerId, ...] = (), coefficient: str = "1") -> Unit:
    unit_id = UnitId.generate()
    return Unit(
        id=unit_id,
        identifier=f"unit-{unit_id.value}",
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
        owner_ids=owner_ids,
    )


def make_community(units: tuple[Unit, ...] = ()) -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value="H12345674"),
        units=units,
    )


def make_account(owner_id: OwnerId | None) -> Account:
    return Account(
        id=AccountId.generate(),
        email=Email(value=f"{uuid4()}@example.com"),
        password_hash="hashed-value",  # pragma: allowlist secret
        owner_id=owner_id,
    )


def make_vote(community_id: CommunityId, options: tuple[VoteOption, ...]) -> Vote:
    return Vote.create(
        id=VoteId.generate(),
        community_id=community_id,
        title="¿Aprobar el presupuesto?",
        description="Votación sobre el presupuesto anual",
        options=options,
        end_date=END_DATE,
        created_by_account_id=AccountId.generate(),
        now=CREATION_NOW,
    )


def make_ballot(vote_id: VoteId, unit_id: UnitId, option_id: VoteOptionId) -> Ballot:
    return Ballot.create(
        id=BallotId.generate(),
        vote_id=vote_id,
        unit_id=unit_id,
        option_id=option_id,
        cast_by_owner_id=OwnerId.generate(),
        now=CREATION_NOW,
    )


def build_repositories() -> tuple[
    InMemoryVoteRepository,
    InMemoryBallotRepository,
    InMemoryAccountRepository,
    InMemoryCommunityRepository,
]:
    return (
        InMemoryVoteRepository(),
        InMemoryBallotRepository(),
        InMemoryAccountRepository(),
        InMemoryCommunityRepository(),
    )


@pytest.mark.asyncio
async def test_closes_vote_and_tallies_ballots_across_options() -> None:
    owner_id = OwnerId.generate()
    unit_yes_1 = make_unit(owner_ids=(OwnerId.generate(),), coefficient="0.3")
    unit_yes_2 = make_unit(owner_ids=(OwnerId.generate(),), coefficient="0.2")
    unit_no = make_unit(owner_ids=(OwnerId.generate(),), coefficient="0.49")
    closer_unit = make_unit(owner_ids=(owner_id,), coefficient="0.01")
    community = make_community((unit_yes_1, unit_yes_2, unit_no, closer_unit))
    account = make_account(owner_id)
    option_yes = VoteOption(id=VoteOptionId.generate(), label="Sí")
    option_no = VoteOption(id=VoteOptionId.generate(), label="No")
    vote = make_vote(community.id, (option_yes, option_no))

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)
    await ballot_repo.save(make_ballot(vote.id, unit_yes_1.id, option_yes.id))
    await ballot_repo.save(make_ballot(vote.id, unit_yes_2.id, option_yes.id))
    await ballot_repo.save(make_ballot(vote.id, unit_no.id, option_no.id))

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)
    result = await use_case.execute(
        vote_id=vote.id.value,
        account_id=account.id.value,
        now=AFTER_END_DATE,
    )

    tallies_by_option = {tally.option_id: tally for tally in result.tallies}
    assert tallies_by_option[option_yes.id].unit_count == 2
    assert tallies_by_option[option_yes.id].weighted_coefficient == Decimal("0.5")
    assert tallies_by_option[option_no.id].unit_count == 1
    assert tallies_by_option[option_no.id].weighted_coefficient == Decimal("0.49")
    assert result.total_units_in_community == 4
    assert result.units_that_voted == 3
    assert result.closed_at == AFTER_END_DATE


@pytest.mark.asyncio
async def test_raises_vote_not_found_error_when_vote_missing() -> None:
    owner_id = OwnerId.generate()
    account = make_account(owner_id)
    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await account_repo.save(account)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteNotFoundError):
        await use_case.execute(
            vote_id=uuid4(),
            account_id=account.id.value,
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_vote_has_not_ended_yet_error_when_now_equals_end_date() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteHasNotEndedYetError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_vote_has_not_ended_yet_error_when_now_before_end_date() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteHasNotEndedYetError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=BEFORE_END_DATE,
        )


@pytest.mark.asyncio
async def test_vote_has_not_ended_yet_check_precedes_account_lookup() -> None:
    community = make_community((make_unit(),))
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteHasNotEndedYetError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=uuid4(),
            now=BEFORE_END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_account_not_found_error_when_account_missing() -> None:
    community = make_community((make_unit(),))
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotFoundError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=uuid4(),
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_account_has_no_owner() -> None:
    community = make_community((make_unit(),))
    account = make_account(owner_id=None)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotAuthorizedToCloseVoteError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_community_not_found_error_when_community_missing() -> None:
    owner_id = OwnerId.generate()
    account = make_account(owner_id)
    vote = make_vote(
        CommunityId.generate(),
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_owner_has_no_unit_in_community() -> (
    None
):
    owner_id = OwnerId.generate()
    other_owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(other_owner_id,)),))
    account = make_account(owner_id)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotAuthorizedToCloseVoteError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_closing_an_already_closed_vote_raises_vote_already_closed_error() -> (
    None
):
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)

    await use_case.execute(
        vote_id=vote.id.value,
        account_id=account.id.value,
        now=AFTER_END_DATE,
    )

    with pytest.raises(VoteAlreadyClosedError):
        await use_case.execute(
            vote_id=vote.id.value,
            account_id=account.id.value,
            now=AFTER_END_DATE,
        )


@pytest.mark.asyncio
async def test_successful_close_persists_result_on_vote_repository() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(
        community.id,
        (
            VoteOption(id=VoteOptionId.generate(), label="Sí"),
            VoteOption(id=VoteOptionId.generate(), label="No"),
        ),
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CloseVote(vote_repo, ballot_repo, account_repo, community_repo)
    result = await use_case.execute(
        vote_id=vote.id.value,
        account_id=account.id.value,
        now=AFTER_END_DATE,
    )

    persisted_vote = await vote_repo.get_by_id(vote.id)
    assert persisted_vote is not None
    assert persisted_vote.result == result
