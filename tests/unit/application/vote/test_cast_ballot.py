from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.vote.cast_ballot import (
    AccountNotAuthorizedToCastBallotError,
    AccountNotFoundError,
    CastBallot,
    CommunityNotFoundError,
    OptionDoesNotBelongToVoteError,
    UnitAlreadyVotedByAnotherOwnerError,
    UnitNotFoundInCommunityError,
    VoteHasEndedError,
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
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import Vote
from src.domain.vote.vote_option import VoteOption
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_ballot_repository import InMemoryBallotRepository
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository
from tests.fakes.in_memory_vote_repository import InMemoryVoteRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FUTURE_END_DATE = datetime(2026, 6, 1, tzinfo=timezone.utc)
CREATION_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
ALREADY_PASSED_END_DATE = datetime(2025, 6, 1, tzinfo=timezone.utc)


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(owner_ids: tuple[OwnerId, ...] = ()) -> Unit:
    unit_id = UnitId.generate()
    return Unit(
        id=unit_id,
        identifier=f"unit-{unit_id.value}",
        participation_coefficient=ParticipationCoefficient(value=Decimal("1")),
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


def make_vote(
    community_id: CommunityId,
    created_by_account_id: AccountId,
    end_date: datetime = FUTURE_END_DATE,
    creation_now: datetime = NOW,
) -> Vote:
    options = (
        VoteOption(id=VoteOptionId.generate(), label="Sí"),
        VoteOption(id=VoteOptionId.generate(), label="No"),
    )
    return Vote.create(
        id=VoteId.generate(),
        community_id=community_id,
        title="¿Aprobar el presupuesto?",
        description="Votación sobre el presupuesto anual",
        options=options,
        end_date=end_date,
        created_by_account_id=created_by_account_id,
        now=creation_now,
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
async def test_casts_ballot_when_no_previous_ballot_exists() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)
    chosen_option = vote.options[0]
    ballot_id = await use_case.execute(
        vote_id=vote.id.value,
        unit_id=unit.id.value,
        option_id=chosen_option.id.value,
        account_id=account.id.value,
        now=NOW,
    )

    ballot = await ballot_repo.get_active_ballot(vote.id, unit.id)
    assert ballot is not None
    assert ballot.id == ballot_id
    assert ballot.option_id == chosen_option.id
    assert ballot.cast_by_owner_id == owner_id
    assert ballot.superseded_by_ballot_id is None


@pytest.mark.asyncio
async def test_raises_vote_not_found_error_when_vote_missing() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteNotFoundError):
        await use_case.execute(
            vote_id=uuid4(),
            unit_id=unit.id.value,
            option_id=uuid4(),
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_community_not_found_error_when_community_missing() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    account = make_account(owner_id)
    vote = make_vote(CommunityId.generate(), AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_vote_has_ended_error_when_now_after_end_date() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    vote = make_vote(
        community.id,
        AccountId.generate(),
        end_date=ALREADY_PASSED_END_DATE,
        creation_now=CREATION_NOW,
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteHasEndedError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=uuid4(),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_vote_has_ended_check_precedes_account_lookup() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    vote = make_vote(
        community.id,
        AccountId.generate(),
        end_date=ALREADY_PASSED_END_DATE,
        creation_now=CREATION_NOW,
    )

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(VoteHasEndedError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=uuid4(),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_account_not_found_error_when_account_missing() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotFoundError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=uuid4(),
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_account_has_no_owner() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id=None)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotAuthorizedToCastBallotError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_option_does_not_belong_to_vote_error() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(OptionDoesNotBelongToVoteError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=uuid4(),
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_unit_not_found_in_community_error() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(UnitNotFoundInCommunityError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=uuid4(),
            option_id=vote.options[0].id.value,
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_owner_does_not_own_the_unit() -> None:
    owner_id = OwnerId.generate()
    other_owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(other_owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    with pytest.raises(AccountNotAuthorizedToCastBallotError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[0].id.value,
            account_id=account.id.value,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_same_owner_changing_vote_supersedes_previous_ballot() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    first_ballot_id = await use_case.execute(
        vote_id=vote.id.value,
        unit_id=unit.id.value,
        option_id=vote.options[0].id.value,
        account_id=account.id.value,
        now=NOW,
    )

    second_ballot_id = await use_case.execute(
        vote_id=vote.id.value,
        unit_id=unit.id.value,
        option_id=vote.options[1].id.value,
        account_id=account.id.value,
        now=NOW,
    )

    assert first_ballot_id != second_ballot_id

    first_ballot = next(b for b in ballot_repo.all() if b.id == first_ballot_id)
    assert first_ballot.superseded_by_ballot_id == second_ballot_id

    active_ballot = await ballot_repo.get_active_ballot(vote.id, unit.id)
    assert active_ballot is not None
    assert active_ballot.id == second_ballot_id
    assert active_ballot.option_id == vote.options[1].id


@pytest.mark.asyncio
async def test_different_owner_voting_over_already_voted_unit_raises_error() -> None:
    owner_id = OwnerId.generate()
    co_owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id, co_owner_id))
    community = make_community((unit,))
    account = make_account(owner_id)
    co_owner_account = make_account(co_owner_id)
    vote = make_vote(community.id, AccountId.generate())

    vote_repo, ballot_repo, account_repo, community_repo = build_repositories()
    await vote_repo.save(vote)
    await account_repo.save(account)
    await account_repo.save(co_owner_account)
    await community_repo.save(community)

    use_case = CastBallot(vote_repo, ballot_repo, account_repo, community_repo)

    first_ballot_id = await use_case.execute(
        vote_id=vote.id.value,
        unit_id=unit.id.value,
        option_id=vote.options[0].id.value,
        account_id=account.id.value,
        now=NOW,
    )

    with pytest.raises(UnitAlreadyVotedByAnotherOwnerError):
        await use_case.execute(
            vote_id=vote.id.value,
            unit_id=unit.id.value,
            option_id=vote.options[1].id.value,
            account_id=co_owner_account.id.value,
            now=NOW,
        )

    original_ballot = next(b for b in ballot_repo.all() if b.id == first_ballot_id)
    assert original_ballot.superseded_by_ballot_id is None
