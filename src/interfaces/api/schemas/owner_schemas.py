from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CreateOwnerRequest(BaseModel):
    nif: str
    full_name: str
    email: str
    phone: str | None = None


class OwnerResponse(BaseModel):
    id: UUID
    nif: str
    full_name: str
    email: str
    phone: str | None = None
