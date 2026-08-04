from __future__ import annotations

from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict


class AggregateId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @classmethod
    def generate(cls) -> Self:
        return cls(value=uuid4())
