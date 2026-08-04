from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from src.interfaces.api.schemas.community_schemas import AddressResponse


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


class OwnerUnitResponse(BaseModel):
    id: UUID
    identifier: str
    participation_coefficient: Decimal
    community_id: UUID
    community_name: str
    community_address: AddressResponse
