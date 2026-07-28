from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.domain.owner.value_objects import OwnerId

from .value_objects import ParticipationCoefficient, UnitId


class Unit(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UnitId
    participation_coefficient: ParticipationCoefficient
    owner_ids: tuple[OwnerId, ...] = ()
