import pytest

from src.application.identity.register_account import (
    OwnerAlreadyLinkedError,
    OwnerNotFoundError,
    RegisterAccount,
)
from src.application.identity.security import verify_password
from src.domain.identity.account import DuplicateEmailError
from src.domain.owner.owner import Owner
from src.domain.owner.value_objects import NIF
from src.domain.owner.value_objects import Email as OwnerEmail
from src.domain.owner.value_objects import OwnerId
from tests.fakes.in_memory_account_repository import InMemoryAccountRepository
from tests.fakes.in_memory_owner_repository import InMemoryOwnerRepository


async def _persist_owner(owner_repository: InMemoryOwnerRepository) -> OwnerId:
    owner = Owner(
        id=OwnerId.generate(),
        nif=NIF(value="12345678Z"),
        full_name="Juan Garcia",
        email=OwnerEmail(value="juan.garcia@example.com"),
    )
    await owner_repository.save(owner)
    return owner.id


@pytest.mark.asyncio
async def test_registers_account_and_persists_it() -> None:
    repository = InMemoryAccountRepository()
    use_case = RegisterAccount(repository, InMemoryOwnerRepository())

    account_id = await use_case.execute(
        email="jane.doe@example.com", password="s3cret-password"
    )

    persisted = await repository.get_by_id(account_id)
    assert persisted is not None
    assert persisted.email.value == "jane.doe@example.com"
    assert persisted.owner_id is None


@pytest.mark.asyncio
async def test_registers_account_with_owner_link() -> None:
    repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    owner_id = await _persist_owner(owner_repository)
    use_case = RegisterAccount(repository, owner_repository)

    account_id = await use_case.execute(
        email="jane.doe@example.com",
        password="s3cret-password",
        owner_id=owner_id.value,
    )

    persisted = await repository.get_by_id(account_id)
    assert persisted is not None
    assert persisted.owner_id == owner_id


@pytest.mark.asyncio
async def test_never_persists_the_plaintext_password() -> None:
    repository = InMemoryAccountRepository()
    use_case = RegisterAccount(repository, InMemoryOwnerRepository())

    account_id = await use_case.execute(
        email="jane.doe@example.com", password="s3cret-password"
    )

    persisted = await repository.get_by_id(account_id)
    assert persisted is not None
    assert persisted.password_hash != "s3cret-password"
    assert verify_password("s3cret-password", persisted.password_hash)


@pytest.mark.asyncio
async def test_execute_propagates_duplicate_email_error_and_persists_nothing() -> None:
    repository = InMemoryAccountRepository()
    use_case = RegisterAccount(repository, InMemoryOwnerRepository())
    await use_case.execute(email="jane.doe@example.com", password="s3cret-password")

    with pytest.raises(DuplicateEmailError):
        await use_case.execute(
            email="jane.doe@example.com", password="another-password"
        )

    assert len(repository.all()) == 1


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_invalid_email_and_persists_nothing() -> (
    None
):
    repository = InMemoryAccountRepository()
    use_case = RegisterAccount(repository, InMemoryOwnerRepository())

    with pytest.raises(ValueError):
        await use_case.execute(email="INVALID", password="s3cret-password")

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_raises_owner_not_found_error_and_persists_nothing() -> None:
    repository = InMemoryAccountRepository()
    use_case = RegisterAccount(repository, InMemoryOwnerRepository())
    nonexistent_owner_id = OwnerId.generate()

    with pytest.raises(OwnerNotFoundError):
        await use_case.execute(
            email="jane.doe@example.com",
            password="s3cret-password",
            owner_id=nonexistent_owner_id.value,
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_raises_owner_already_linked_error_and_persists_nothing() -> None:
    repository = InMemoryAccountRepository()
    owner_repository = InMemoryOwnerRepository()
    owner_id = await _persist_owner(owner_repository)
    use_case = RegisterAccount(repository, owner_repository)
    await use_case.execute(
        email="first@example.com", password="s3cret-password", owner_id=owner_id.value
    )

    with pytest.raises(OwnerAlreadyLinkedError):
        await use_case.execute(
            email="second@example.com",
            password="s3cret-password",
            owner_id=owner_id.value,
        )

    assert len(repository.all()) == 1
