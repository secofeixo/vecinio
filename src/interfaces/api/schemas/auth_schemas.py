from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


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
