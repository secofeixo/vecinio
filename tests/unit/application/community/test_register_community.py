from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.community.register_community import RegisterCommunity, UnitInput
from src.domain.community.community import (
    DuplicateCifError,
    DuplicateUnitIdentifierError,
    ParticipationCoefficientSumError,
)
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository


def address_kwargs() -> dict:
    return dict(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


@pytest.mark.asyncio
async def test_registers_community_with_valid_units_and_persists_it() -> None:
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)
    owner_id = uuid4()
    units = [
        UnitInput(
            participation_coefficient=Decimal("0.6"),
            identifier="4º-2ª",
            owner_ids=(owner_id,),
        ),
        UnitInput(participation_coefficient=Decimal("0.4"), identifier="Bajo A"),
    ]

    community_id = await use_case.execute(
        name="Edificio Sol",
        cif="H12345674",
        units=units,
        **address_kwargs(),
    )

    persisted = await repository.get_by_id(community_id)
    assert persisted is not None
    assert persisted.name == "Edificio Sol"
    assert persisted.cif.value == "H12345674"
    assert persisted.address.city == "Madrid"
    assert len(persisted.units) == 2
    coefficients = {unit.participation_coefficient.value for unit in persisted.units}
    assert coefficients == {Decimal("0.6"), Decimal("0.4")}
    unit_with_owner = next(unit for unit in persisted.units if unit.owner_ids)
    assert unit_with_owner.owner_ids[0].value == owner_id


@pytest.mark.asyncio
async def test_registers_community_with_zero_units() -> None:
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)

    community_id = await use_case.execute(
        name="Edificio Luna",
        cif="H12345674",
        units=[],
        **address_kwargs(),
    )

    persisted = await repository.get_by_id(community_id)
    assert persisted is not None
    assert persisted.units == ()


@pytest.mark.asyncio
async def test_propagates_participation_coefficient_sum_error_and_persists_nothing() -> (
    None
):
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)
    units = [
        UnitInput(participation_coefficient=Decimal("0.5"), identifier="4º-2ª"),
        UnitInput(participation_coefficient=Decimal("0.4"), identifier="Bajo A"),
    ]

    with pytest.raises(ParticipationCoefficientSumError):
        await use_case.execute(
            name="Edificio Fallido",
            cif="H12345674",
            units=units,
            **address_kwargs(),
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_invalid_cif_and_persists_nothing() -> (
    None
):
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            name="Edificio Fallido",
            cif="INVALID",
            units=[],
            **address_kwargs(),
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_value_error_for_duplicate_unit_ids_and_persists_nothing() -> (
    None
):
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)
    shared_unit_id = uuid4()
    units = [
        UnitInput(
            participation_coefficient=Decimal("0.5"),
            identifier="4º-2ª",
            unit_id=shared_unit_id,
        ),
        UnitInput(
            participation_coefficient=Decimal("0.5"),
            identifier="Bajo A",
            unit_id=shared_unit_id,
        ),
    ]

    with pytest.raises(ValueError):
        await use_case.execute(
            name="Edificio Fallido",
            cif="H12345674",
            units=units,
            **address_kwargs(),
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_duplicate_unit_identifier_error_and_persists_nothing() -> (
    None
):
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)
    units = [
        UnitInput(participation_coefficient=Decimal("0.5"), identifier="4º-2ª"),
        UnitInput(participation_coefficient=Decimal("0.5"), identifier="4º-2ª"),
    ]

    with pytest.raises(DuplicateUnitIdentifierError):
        await use_case.execute(
            name="Edificio Fallido",
            cif="H12345674",
            units=units,
            **address_kwargs(),
        )

    assert repository.all() == ()


@pytest.mark.asyncio
async def test_execute_propagates_duplicate_cif_error_and_persists_nothing() -> None:
    repository = InMemoryCommunityRepository()
    use_case = RegisterCommunity(repository)
    await use_case.execute(
        name="Edificio Sol",
        cif="H12345674",
        units=[],
        **address_kwargs(),
    )

    with pytest.raises(DuplicateCifError):
        await use_case.execute(
            name="Edificio Luna",
            cif="H12345674",
            units=[],
            **address_kwargs(),
        )

    assert len(repository.all()) == 1
    assert repository.all()[0].name == "Edificio Sol"
