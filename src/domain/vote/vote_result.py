from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .value_objects import VoteOptionId


class OptionTally(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_id: VoteOptionId
    unit_count: int
    weighted_coefficient: Decimal


class VoteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tallies: tuple[OptionTally, ...]
    total_units_in_community: int
    units_that_voted: int
    total_participation_coefficient: Decimal
    closed_at: datetime
