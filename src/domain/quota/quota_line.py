from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class QuotaLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    concept: str
    amount: Decimal
