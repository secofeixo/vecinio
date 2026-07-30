from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict


class CommunityGroupId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> CommunityGroupId:
        return CommunityGroupId(value=uuid4())
