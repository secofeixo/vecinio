from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.domain.community.value_objects import UnitId


class QuotaAllocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UnitId
    participation_coefficient: Decimal
    amount: Decimal
