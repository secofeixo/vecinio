from decimal import Decimal

import pytest

from src.domain.community.community import (
    Community,
    OwnerAlreadyAssignedError,
    ParticipationCoefficientSumError,
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
from src.domain.owner.value_objects import OwnerId


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(coefficient: str, unit_id: UnitId | None = None) -> Unit:
    return Unit(
        id=unit_id or UnitId.generate(),
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
    )


def make_community(units: list[Unit]) -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value="H12345674"),
        units=tuple(units),
    )


def test_registers_community_with_zero_units() -> None:
    community = make_community([])

    assert community.units == ()


def test_registers_community_with_units_summing_to_one() -> None:
    units = [make_unit("0.3"), make_unit("0.3"), make_unit("0.4")]

    community = make_community(units)

    assert community.units == tuple(units)


def test_registration_rejects_units_not_summing_to_one() -> None:
    units = [make_unit("0.5"), make_unit("0.4")]

    with pytest.raises(ParticipationCoefficientSumError):
        make_community(units)


def test_registration_rejects_duplicate_unit_ids() -> None:
    shared_id = UnitId.generate()
    units = [make_unit("0.5", shared_id), make_unit("0.5", shared_id)]

    with pytest.raises(ValueError):
        make_community(units)


def test_redefine_units_from_empty_to_single_full_unit_succeeds() -> None:
    community = make_community([])
    unit = make_unit("1")

    community.redefine_units([unit])

    assert community.units == (unit,)


def test_redefine_units_rejects_when_new_set_does_not_sum_to_one() -> None:
    community = make_community([])

    with pytest.raises(ParticipationCoefficientSumError):
        community.redefine_units([make_unit("0.5")])


def test_redefine_units_allows_rebalancing_existing_units() -> None:
    unit_a_id = UnitId.generate()
    unit_b_id = UnitId.generate()
    community = make_community(
        [make_unit("0.5", unit_a_id), make_unit("0.5", unit_b_id)]
    )

    rebalanced = [make_unit("0.6", unit_a_id), make_unit("0.4", unit_b_id)]
    community.redefine_units(rebalanced)

    assert community.units == tuple(rebalanced)


def test_redefine_units_rejects_duplicate_ids_in_new_set() -> None:
    community = make_community([])
    shared_id = UnitId.generate()

    with pytest.raises(ValueError):
        community.redefine_units(
            [make_unit("0.5", shared_id), make_unit("0.5", shared_id)]
        )


def test_community_preserves_previous_valid_state_after_failed_redefine() -> None:
    units = [make_unit("0.5"), make_unit("0.5")]
    community = make_community(units)

    with pytest.raises(ParticipationCoefficientSumError):
        community.redefine_units([make_unit("0.5")])

    assert community.units == tuple(units)


def test_assign_owner_to_unit_succeeds_for_existing_unit() -> None:
    unit = make_unit("1")
    community = make_community([unit])
    owner_id = OwnerId.generate()

    community.assign_owner_to_unit(unit.id, owner_id)

    updated_unit = community.units[0]
    assert updated_unit.owner_ids == (owner_id,)
    assert updated_unit.id == unit.id
    assert updated_unit.participation_coefficient == unit.participation_coefficient


def test_assign_owner_to_unit_raises_when_unit_not_found() -> None:
    community = make_community([make_unit("1")])

    with pytest.raises(UnitNotFoundError):
        community.assign_owner_to_unit(UnitId.generate(), OwnerId.generate())


def test_assign_owner_to_unit_raises_when_owner_already_assigned() -> None:
    owner_id = OwnerId.generate()
    unit = Unit(
        id=UnitId.generate(),
        participation_coefficient=ParticipationCoefficient(value=Decimal("1")),
        owner_ids=(owner_id,),
    )
    community = make_community([unit])

    with pytest.raises(OwnerAlreadyAssignedError):
        community.assign_owner_to_unit(unit.id, owner_id)


def test_assign_owner_to_unit_allows_second_different_owner_co_ownership() -> None:
    owner_a = OwnerId.generate()
    owner_b = OwnerId.generate()
    unit = Unit(
        id=UnitId.generate(),
        participation_coefficient=ParticipationCoefficient(value=Decimal("1")),
        owner_ids=(owner_a,),
    )
    community = make_community([unit])

    community.assign_owner_to_unit(unit.id, owner_b)

    assert community.units[0].owner_ids == (owner_a, owner_b)


def test_assign_owner_to_unit_leaves_other_units_untouched() -> None:
    unit_a = make_unit("0.5")
    unit_b = make_unit("0.5")
    community = make_community([unit_a, unit_b])

    community.assign_owner_to_unit(unit_a.id, OwnerId.generate())

    untouched = next(unit for unit in community.units if unit.id == unit_b.id)
    assert untouched.owner_ids == ()
    assert untouched.participation_coefficient == unit_b.participation_coefficient
