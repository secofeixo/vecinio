from __future__ import annotations

from pydantic import BaseModel, Field

from src.domain.owner.value_objects import OwnerId

from .value_objects import ParticipationCoefficient, UnitId


class Unit(BaseModel):
    id: UnitId
    participation_coefficient: ParticipationCoefficient
    owner_ids: list[OwnerId] = Field(default_factory=list)
