from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from .value_objects import VoteOptionId


class VoteOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: VoteOptionId
    label: str

    @field_validator("label")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Vote option label must not be empty")
        return value
