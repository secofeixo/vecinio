from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from src.domain.owner.value_objects import OwnerId

from .unit import Unit
from .value_objects import CIF, Address, CommunityId, ParticipationCoefficient, UnitId


class CommunityDomainError(Exception):
    pass


class ParticipationCoefficientSumError(CommunityDomainError):
    pass


class DuplicateCifError(CommunityDomainError):
    pass


class UnitNotFoundError(CommunityDomainError):
    pass


class OwnerAlreadyAssignedError(CommunityDomainError):
    pass


class ConcurrentModificationError(CommunityDomainError):
    pass


class Community(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: CommunityId
    name: str
    address: Address
    cif: CIF
    units: tuple[Unit, ...] = ()
    version: int = 0

    @model_validator(mode="after")
    def _check_invariants(self) -> Community:
        self._check_units_are_valid(self.units)
        return self

    def redefine_units(self, units: Iterable[Unit]) -> None:
        new_units = tuple(units)
        self._check_units_are_valid(new_units)
        self.units = new_units

    def assign_owner_to_unit(self, unit_id: UnitId, owner_id: OwnerId) -> None:
        target = next((unit for unit in self.units if unit.id == unit_id), None)
        if target is None:
            raise UnitNotFoundError(f"No unit found with id {unit_id}")

        if owner_id in target.owner_ids:
            raise OwnerAlreadyAssignedError(
                f"Owner {owner_id} is already assigned to unit {unit_id}"
            )

        updated_unit = Unit(
            id=target.id,
            participation_coefficient=target.participation_coefficient,
            owner_ids=target.owner_ids + (owner_id,),
        )
        self.redefine_units(
            updated_unit if unit.id == unit_id else unit for unit in self.units
        )

    @staticmethod
    def _check_units_are_valid(units: tuple[Unit, ...]) -> None:
        ids = [unit.id for unit in units]
        if len(ids) != len(set(ids)):
            raise ValueError("Unit ids must be unique within a community")

        if not units:
            return

        total = ParticipationCoefficient.total(
            unit.participation_coefficient for unit in units
        )
        if total != ParticipationCoefficient.FULL:
            raise ParticipationCoefficientSumError(
                f"Participation coefficients must sum to "
                f"{ParticipationCoefficient.FULL}, got {total}"
            )
