from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.login import Login
from src.application.identity.logout import Logout
from src.application.identity.refresh_access_token import RefreshAccessToken
from src.application.identity.register_account import RegisterAccount
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository
from src.infrastructure.persistence.refresh_token_repository import (
    PostgresRefreshTokenRepository,
)
from src.interfaces.api.dependencies import get_session
from src.interfaces.api.schemas.auth_schemas import (
    AccessTokenResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterAccountRequest,
    RegisterAccountResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterAccountRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> RegisterAccountResponse:
    repository = PostgresAccountRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    use_case = RegisterAccount(repository, owner_repository)

    account_id = await use_case.execute(
        email=request.email,
        password=request.password,
        owner_id=request.owner_id,
    )

    return RegisterAccountResponse(id=account_id.value)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TokenResponse:
    account_repository = PostgresAccountRepository(session)
    refresh_token_repository = PostgresRefreshTokenRepository(session)
    use_case = Login(account_repository, refresh_token_repository)

    tokens = await use_case.execute(email=request.email, password=request.password)

    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AccessTokenResponse:
    repository = PostgresRefreshTokenRepository(session)
    use_case = RefreshAccessToken(repository)

    access_token = await use_case.execute(refresh_token=request.refresh_token)

    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    repository = PostgresRefreshTokenRepository(session)
    use_case = Logout(repository)

    await use_case.execute(refresh_token=request.refresh_token)
