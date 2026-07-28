from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .value_objects import NIF, Email, OwnerId, PhoneNumber


class OwnerDomainError(Exception):
    pass


class DuplicateNifError(OwnerDomainError):
    pass


class Owner(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: OwnerId
    nif: NIF
    full_name: str
    email: Email
    phone: PhoneNumber | None = None
