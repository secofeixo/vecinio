from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.domain.owner.value_objects import OwnerId

from .value_objects import AccountId, Email


class IdentityDomainError(Exception):
    pass


class DuplicateEmailError(IdentityDomainError):
    pass


class ConcurrentModificationError(IdentityDomainError):
    pass


class Account(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: AccountId
    email: Email
    password_hash: str
    owner_id: OwnerId | None = None
    version: int = 0
