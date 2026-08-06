import pytest

from src.application.identity.link_owner_to_account import (
    AccountNotFoundError,
    LinkOwnerToAccount,
    OwnerAlreadyLinkedError,
    OwnerNotFoundError,
)
from src.domain.identity.account import Account, AccountAlreadyHasOwnerError
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.owner import Owner
from src.domain.owner.value_objects import NIF
from src.domain.owner.value_objects import Email as OwnerEmail
from src.domain.owner.value_objects import OwnerId
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_owner_repository import InMemoryOwnerRepository


class SpyOwnerRepository(InMemoryOwnerRepository):
    def __init__(self) -> None:
        super().__init__()
        self.get_by_nif_calls = 0

    async def get_by_nif(self, nif: NIF) -> Owner | None:
        self.get_by_nif_calls += 1
        return await super().get_by_nif(nif)


async def _persist_account(
    account_repository: InMemoryAccountRepository,
    *,
    owner_id: OwnerId | None = None,
) -> AccountId:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",  # pragma: allowlist secret
        owner_id=owner_id,
    )
    await account_repository.save(account)
    return account.id


async def _persist_owner(
    owner_repository: InMemoryOwnerRepository, *, nif: str = "12345678Z"
) -> Owner:
    owner = Owner(
        id=OwnerId.generate(),
        nif=NIF(value=nif),
        full_name="Juan Garcia",
        email=OwnerEmail(value="juan.garcia@example.com"),
    )
    await owner_repository.save(owner)
    return owner


@pytest.mark.asyncio
async def test_execute_links_owner_to_account() -> None:
    account_repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    account_id = await _persist_account(account_repository)
    owner = await _persist_owner(owner_repository)
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    await use_case.execute(account_id=account_id.value, nif=owner.nif.value)

    persisted = await account_repository.get_by_id(account_id)
    assert persisted is not None
    assert persisted.owner_id == owner.id


@pytest.mark.asyncio
async def test_execute_raises_account_not_found_error() -> None:
    account_repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    owner = await _persist_owner(owner_repository)
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    with pytest.raises(AccountNotFoundError):
        await use_case.execute(
            account_id=AccountId.generate().value, nif=owner.nif.value
        )


@pytest.mark.asyncio
async def test_execute_raises_account_already_has_owner_error_before_looking_up_nif() -> (
    None
):
    account_repository = InMemoryAccountRepository()
    owner_repository = SpyOwnerRepository()
    account_id = await _persist_account(account_repository, owner_id=OwnerId.generate())
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    with pytest.raises(AccountAlreadyHasOwnerError):
        await use_case.execute(account_id=account_id.value, nif="12345678Z")

    assert owner_repository.get_by_nif_calls == 0


@pytest.mark.asyncio
async def test_execute_raises_owner_not_found_error_for_unknown_nif() -> None:
    account_repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    account_id = await _persist_account(account_repository)
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    with pytest.raises(OwnerNotFoundError):
        await use_case.execute(account_id=account_id.value, nif="12345678Z")

    persisted = await account_repository.get_by_id(account_id)
    assert persisted is not None
    assert persisted.owner_id is None


@pytest.mark.asyncio
async def test_execute_raises_owner_already_linked_error() -> None:
    account_repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    owner = await _persist_owner(owner_repository)
    await _persist_account(account_repository, owner_id=owner.id)
    unlinked_account_id = await _persist_account(account_repository)
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    with pytest.raises(OwnerAlreadyLinkedError):
        await use_case.execute(
            account_id=unlinked_account_id.value, nif=owner.nif.value
        )

    persisted = await account_repository.get_by_id(unlinked_account_id)
    assert persisted is not None
    assert persisted.owner_id is None
