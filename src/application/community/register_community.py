from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from src.domain.community.community import Community, DuplicateCifError
from src.domain.community.repository import CommunityRepository
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.owner.value_objects import OwnerId


@dataclass(frozen=True)
class UnitInput:
    participation_coefficient: Decimal
    unit_id: UUID | None = None
    owner_ids: tuple[UUID, ...] = field(default_factory=tuple)


class RegisterCommunity:
    def __init__(self, repository: CommunityRepository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        name: str,
        street: str,
        number: str,
        city: str,
        postal_code: str,
        province: str,
        cif: str,
        units: Iterable[UnitInput] = (),
    ) -> CommunityId:
        cif_vo = CIF(value=cif)
        if self._repository.exists_by_cif(cif_vo):
            raise DuplicateCifError(
                f"A community with CIF {cif_vo.value} already exists"
            )

        community = Community(
            id=CommunityId.generate(),
            name=name,
            address=Address(
                street=street,
                number=number,
                city=city,
                postal_code=postal_code,
                province=province,
            ),
            cif=cif_vo,
            units=tuple(self._to_unit(unit) for unit in units),
        )

        self._repository.save(community)
        return community.id

    @staticmethod
    def _to_unit(unit: UnitInput) -> Unit:
        return Unit(
            id=(
                UnitId(value=unit.unit_id)
                if unit.unit_id is not None
                else UnitId.generate()
            ),
            participation_coefficient=ParticipationCoefficient(
                value=unit.participation_coefficient
            ),
            owner_ids=tuple(OwnerId(value=owner_id) for owner_id in unit.owner_ids),
        )
