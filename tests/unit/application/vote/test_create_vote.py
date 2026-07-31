from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.vote.create_vote import (
    AccountNotAuthorizedToCreateVoteError,
    AccountNotFoundError,
    CommunityNotFoundError,
    CreateVote,
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
from src.domain.vote.vote import (
    DuplicateVoteOptionLabelError,
    EmptyVoteTitleError,
    InsufficientVoteOptionsError,
    VoteEndDateNotInFutureError,
)
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository
from tests.fakes.in_memory_vote_repository import InMemoryVoteRepository

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FUTURE_END_DATE = datetime(2026, 6, 1, tzinfo=timezone.utc)


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


def build_repositories() -> (
    tuple[
        InMemoryVoteRepository, InMemoryAccountRepository, InMemoryCommunityRepository
    ]
):
    return (
        InMemoryVoteRepository(),
        InMemoryAccountRepository(),
        InMemoryCommunityRepository(),
    )


@pytest.mark.asyncio
async def test_creates_vote_when_account_owns_a_unit_in_the_community() -> None:
    owner_id = OwnerId.generate()
    unit = make_unit(owner_ids=(owner_id,))
    community = make_community((unit,))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)
    vote_id = await use_case.execute(
        community_id=community.id.value,
        account_id=account.id.value,
        title="¿Aprobar el presupuesto?",
        description="Votación sobre el presupuesto anual",
        option_labels=["Sí", "No"],
        end_date=FUTURE_END_DATE,
        now=NOW,
    )

    vote = await vote_repository.get_by_id(vote_id)
    assert vote is not None
    assert vote.community_id == community.id
    assert vote.created_by_account_id == account.id
    assert [option.label for option in vote.options] == ["Sí", "No"]


@pytest.mark.asyncio
async def test_raises_account_not_found_error_when_account_missing() -> None:
    community = make_community((make_unit(),))
    vote_repository, account_repository, community_repository = build_repositories()
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(AccountNotFoundError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=uuid4(),
            title="Título",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_account_has_no_owner() -> None:
    community = make_community((make_unit(),))
    account = make_account(owner_id=None)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(AccountNotAuthorizedToCreateVoteError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_community_not_found_error_when_community_missing() -> None:
    owner_id = OwnerId.generate()
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            community_id=uuid4(),
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_raises_not_authorized_error_when_owner_has_no_unit_in_community() -> (
    None
):
    owner_id = OwnerId.generate()
    other_owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(other_owner_id,)),))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(AccountNotAuthorizedToCreateVoteError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_propagates_insufficient_options_error_unchanged() -> None:
    owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(owner_id,)),))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(InsufficientVoteOptionsError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Solo una opción"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_propagates_duplicate_option_label_error_unchanged() -> None:
    owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(owner_id,)),))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(DuplicateVoteOptionLabelError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Sí", "Sí"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_propagates_empty_title_error_unchanged() -> None:
    owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(owner_id,)),))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(EmptyVoteTitleError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="   ",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=FUTURE_END_DATE,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_propagates_end_date_not_in_future_error_unchanged() -> None:
    owner_id = OwnerId.generate()
    community = make_community((make_unit(owner_ids=(owner_id,)),))
    account = make_account(owner_id)

    vote_repository, account_repository, community_repository = build_repositories()
    await account_repository.save(account)
    await community_repository.save(community)

    use_case = CreateVote(vote_repository, account_repository, community_repository)

    with pytest.raises(VoteEndDateNotInFutureError):
        await use_case.execute(
            community_id=community.id.value,
            account_id=account.id.value,
            title="Título",
            description="Descripción",
            option_labels=["Sí", "No"],
            end_date=NOW,
            now=NOW,
        )
