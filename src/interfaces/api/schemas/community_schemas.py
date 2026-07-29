from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class UnitRequest(BaseModel):
    participation_coefficient: Decimal
    unit_id: UUID | None = None
    owner_ids: list[UUID] = []


class CreateCommunityRequest(BaseModel):
    name: str
    street: str
    number: str
    city: str
    postal_code: str
    province: str
    cif: str
    units: list[UnitRequest] = []


class AddressResponse(BaseModel):
    street: str
    number: str
    city: str
    postal_code: str
    province: str


class UnitResponse(BaseModel):
    id: UUID
    participation_coefficient: Decimal
    owner_ids: list[UUID]


class CommunityResponse(BaseModel):
    id: UUID
    name: str
    address: AddressResponse
    cif: str
    units: list[UnitResponse]
