from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, model_validator

from .unit import Unit
from .value_objects import CIF, Address, CommunityId, ParticipationCoefficient


class CommunityDomainError(Exception):
    pass


class ParticipationCoefficientSumError(CommunityDomainError):
    pass


class DuplicateCifError(CommunityDomainError):
    pass


class Community(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: CommunityId
    name: str
    address: Address
    cif: CIF
    units: tuple[Unit, ...] = ()

    @model_validator(mode="after")
    def _check_invariants(self) -> Community:
        self._check_units_are_valid(self.units)
        return self

    def redefine_units(self, units: Iterable[Unit]) -> None:
        new_units = tuple(units)
        self._check_units_are_valid(new_units)
        self.units = new_units

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
