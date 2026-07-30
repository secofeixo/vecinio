from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CreateCommunityGroupRequest(BaseModel):
    name: str
    community_ids: list[UUID]


class CommunityGroupResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    member_community_ids: list[UUID]
