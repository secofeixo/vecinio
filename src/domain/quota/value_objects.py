from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict


class QuotaId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> QuotaId:
        return QuotaId(value=uuid4())


class QuotaType(str, Enum):
    ORDINARY = "ordinary"
    EXTRAORDINARY = "extraordinary"
