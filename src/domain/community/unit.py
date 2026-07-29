from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from src.domain.owner.value_objects import OwnerId

from .value_objects import ParticipationCoefficient, UnitId


class Unit(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UnitId
    identifier: str
    participation_coefficient: ParticipationCoefficient
    owner_ids: tuple[OwnerId, ...] = ()

    @field_validator("identifier")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Unit identifier must not be empty")
        return value
