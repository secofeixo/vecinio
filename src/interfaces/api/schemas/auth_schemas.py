from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.interfaces.api.schemas.owner_schemas import OwnerResponse


class RegisterAccountRequest(BaseModel):
    email: str
    password: str
    owner_id: UUID | None = None


class RegisterAccountResponse(BaseModel):
    id: UUID


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class AccountMeResponse(BaseModel):
    id: UUID
    email: str
    owner: OwnerResponse | None = None


class LinkOwnerRequest(BaseModel):
    nif: str
