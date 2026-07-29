from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.community.assign_owner_to_unit import (
    AssignOwnerToUnit,
    CommunityNotFoundError,
    OwnerNotFoundError,
)
from src.domain.community.community import (
    Community,
    OwnerAlreadyAssignedError,
    UnitNotFoundError,
)
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.owner.owner import Owner
from src.domain.owner.repository import OwnerRepository
from src.domain.owner.value_objects import NIF, Email, OwnerId
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository
from tests.fakes.in_memory_owner_repository import InMemoryOwnerRepository


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(coefficient: str = "1", owner_ids: tuple[OwnerId, ...] = ()) -> Unit:
    return Unit(
        id=UnitId.generate(),
        identifier="4º-2ª",
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
        owner_ids=owner_ids,
    )


def make_community(unit: Unit) -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value="H12345674"),
        units=(unit,),
    )


def make_owner() -> Owner:
    return Owner(
        id=OwnerId.generate(),
        nif=NIF(value="12345678Z"),
        full_name="Jane Doe",
        email=Email(value="jane.doe@example.com"),
    )


class SpyOwnerRepository(OwnerRepository):
    def __init__(self, wrapped: InMemoryOwnerRepository) -> None:
        self._wrapped = wrapped
        self.save_calls = 0

    async def save(self, owner: Owner) -> None:
        self.save_calls += 1
        await self._wrapped.save(owner)

    async def get_by_id(self, owner_id: OwnerId) -> Owner | None:
        return await self._wrapped.get_by_id(owner_id)

    async def exists_by_nif(self, nif: NIF) -> bool:
        return await self._wrapped.exists_by_nif(nif)


@pytest.mark.asyncio
async def test_assigns_owner_to_unit_and_persists_updated_community() -> None:
    unit = make_unit()
    community = make_community(unit)
    owner = make_owner()

    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    owner_repository = InMemoryOwnerRepository()
    await owner_repository.save(owner)

    use_case = AssignOwnerToUnit(community_repository, owner_repository)
    await use_case.execute(
        community_id=community.id.value,
        unit_id=unit.id.value,
        owner_id=owner.id.value,
    )

    persisted = await community_repository.get_by_id(community.id)
    assert persisted is not None
    assert persisted.units[0].owner_ids == (owner.id,)


@pytest.mark.asyncio
async def test_execute_raises_community_not_found_error_when_community_missing() -> (
    None
):
    owner = make_owner()
    community_repository = InMemoryCommunityRepository()
    owner_repository = InMemoryOwnerRepository()
    await owner_repository.save(owner)

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            community_id=uuid4(),
            unit_id=uuid4(),
            owner_id=owner.id.value,
        )


@pytest.mark.asyncio
async def test_execute_raises_owner_not_found_error_when_owner_missing() -> None:
    unit = make_unit()
    community = make_community(unit)
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    owner_repository = InMemoryOwnerRepository()

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(OwnerNotFoundError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=unit.id.value,
            owner_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_execute_propagates_unit_not_found_error() -> None:
    unit = make_unit()
    community = make_community(unit)
    owner = make_owner()
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    owner_repository = InMemoryOwnerRepository()
    await owner_repository.save(owner)

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(UnitNotFoundError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=uuid4(),
            owner_id=owner.id.value,
        )


@pytest.mark.asyncio
async def test_execute_propagates_owner_already_assigned_error() -> None:
    owner = make_owner()
    unit = make_unit(owner_ids=(owner.id,))
    community = make_community(unit)
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    owner_repository = InMemoryOwnerRepository()
    await owner_repository.save(owner)

    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    with pytest.raises(OwnerAlreadyAssignedError):
        await use_case.execute(
            community_id=community.id.value,
            unit_id=unit.id.value,
            owner_id=owner.id.value,
        )


@pytest.mark.asyncio
async def test_execute_never_saves_owner() -> None:
    unit = make_unit()
    community = make_community(unit)
    owner = make_owner()

    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    wrapped_owner_repository = InMemoryOwnerRepository()
    await wrapped_owner_repository.save(owner)
    spy_owner_repository = SpyOwnerRepository(wrapped_owner_repository)

    use_case = AssignOwnerToUnit(community_repository, spy_owner_repository)
    await use_case.execute(
        community_id=community.id.value,
        unit_id=unit.id.value,
        owner_id=owner.id.value,
    )

    assert spy_owner_repository.save_calls == 0
