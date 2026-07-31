from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict


class VoteId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> VoteId:
        return VoteId(value=uuid4())


class VoteOptionId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> VoteOptionId:
        return VoteOptionId(value=uuid4())
