import pytest

from src.application.owner.register_owner import RegisterOwner
from src.domain.owner.owner import DuplicateNifError
from tests.fakes.in_memory_owner_repository import InMemoryOwnerRepository


@pytest.mark.asyncio
async def test_registers_owner_and_persists_it() -> None:
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)

    owner_id = await use_case.execute(
        nif="12345678Z",
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+34612345678",
    )

    persisted = await repository.get_by_id(owner_id)
    assert persisted is not None
    assert persisted.nif.value == "12345678Z"
    assert persisted.full_name == "Jane Doe"
    assert persisted.email.value == "jane.doe@example.com"
    assert persisted.phone is not None
    assert persisted.phone.value == "+34612345678"


@pytest.mark.asyncio
async def test_registers_owner_without_phone() -> None:
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)

    owner_id = await use_case.execute(
        nif="12345678Z",
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone=None,
    )

    persisted = await repository.get_by_id(owner_id)
    assert persisted is not None
    assert persisted.phone is None


@pytest.mark.asyncio
async def test_execute_propagates_duplicate_nif_error_and_persists_nothing() -> None:
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)
    await use_case.execute(
        nif="12345678Z",
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone=None,
    )

    with pytest.raises(DuplicateNifError):
        await use_case.execute(
            nif="12345678Z",
            full_name="John Roe",
            email="john.roe@example.com",
            phone=None,
        )

    assert len(repository.all()) == 1
    assert repository.all()[0].full_name == "Jane Doe"


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_invalid_nif_and_persists_nothing() -> (
    None
):
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            nif="INVALID",
            full_name="Jane Doe",
            email="jane.doe@example.com",
            phone=None,
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_invalid_email_and_persists_nothing() -> (
    None
):
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            nif="12345678Z",
            full_name="Jane Doe",
            email="INVALID",
            phone=None,
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_invalid_phone_and_persists_nothing() -> (
    None
):
    repository = InMemoryOwnerRepository()
    use_case = RegisterOwner(repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            nif="12345678Z",
            full_name="Jane Doe",
            email="jane.doe@example.com",
            phone="INVALID",
        )

    assert repository.all() == ()
