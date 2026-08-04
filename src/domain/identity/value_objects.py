from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator

from src.domain.shared.value_objects import AggregateId


class AccountId(AggregateId):
    pass


class RefreshTokenId(AggregateId):
    pass


class Email(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError(f"Invalid email format: {value}")
        return value
