from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.link_owner_to_account import LinkOwnerToAccount
from src.application.identity.login import Login
from src.application.identity.logout import Logout
from src.application.identity.refresh_access_token import RefreshAccessToken
from src.application.identity.register_account import RegisterAccount
from src.domain.identity.account import Account
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository
from src.infrastructure.persistence.refresh_token_repository import (
    PostgresRefreshTokenRepository,
)
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.auth_schemas import (
    AccessTokenResponse,
    AccountMeResponse,
    LinkOwnerRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterAccountRequest,
    RegisterAccountResponse,
    TokenResponse,
)
from src.interfaces.api.schemas.owner_schemas import OwnerResponse

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post(
    "/register",
    response_model=RegisterAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates a login credential (email + password) in the identity bounded "
        "context. Optionally links to an existing Owner via `owner_id` — an "
        "Account is a separate identity from an Owner, linked only by id, never "
        "merged; each person gets their own Account, even co-owners of the same "
        "unit."
    ),
    responses={
        404: {
            "description": "`owner_id` was provided but no Owner exists with that id."
        },
        409: {"description": "An account with this email already exists."},
        422: {"description": "Request body failed validation."},
    },
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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain access/refresh tokens",
    description=(
        "Verifies email and password and issues a short-lived JWT access token "
        "plus an opaque, hashed, revocable refresh token. Returns the identical "
        "error for an unknown email and for a wrong password — the API never "
        "lets a caller distinguish the two, to avoid turning login into an "
        "account-enumeration oracle."
    ),
    responses={
        401: {
            "description": (
                "Invalid email or password — the same message is returned "
                "whether the email is unregistered or the password is wrong."
            )
        },
        422: {"description": "Request body failed validation."},
    },
)
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


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Exchange a refresh token for a new access token",
    description=(
        "Issues a new short-lived JWT access token if the supplied refresh "
        "token is valid, not expired, and not revoked. The refresh token itself "
        "is not rotated on use in this version."
    ),
    responses={
        401: {"description": "Refresh token is invalid, expired, or revoked."},
        422: {"description": "Request body failed validation."},
    },
)
async def refresh(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AccessTokenResponse:
    repository = PostgresRefreshTokenRepository(session)
    use_case = RefreshAccessToken(repository)

    access_token = await use_case.execute(refresh_token=request.refresh_token)

    return AccessTokenResponse(access_token=access_token)


@router.post(
    "/logout",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
    description=(
        "Revokes the given refresh token so it can no longer be exchanged for "
        "new access tokens."
    ),
    responses={
        401: {"description": "Refresh token is invalid, expired, or revoked."},
        422: {"description": "Request body failed validation."},
    },
)
async def logout(
    request: LogoutRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    repository = PostgresRefreshTokenRepository(session)
    use_case = Logout(repository)

    await use_case.execute(refresh_token=request.refresh_token)


async def _build_account_me_response(
    session: AsyncSession, account: Account
) -> AccountMeResponse:
    owner_response: OwnerResponse | None = None
    if account.owner_id is not None:
        owner_repository = PostgresOwnerRepository(session)
        owner = await owner_repository.get_by_id(account.owner_id)
        if owner is None:
            raise RuntimeError(
                f"Account {account.id.value} references owner_id "
                f"{account.owner_id.value} that does not exist in the database"
            )
        owner_response = OwnerResponse(
            id=owner.id.value,
            nif=owner.nif.value,
            full_name=owner.full_name,
            email=owner.email.value,
            phone=owner.phone.value if owner.phone is not None else None,
        )

    return AccountMeResponse(
        id=account.id.value, email=account.email.value, owner=owner_response
    )


@router.get(
    "/me",
    response_model=AccountMeResponse,
    summary="Get the identity of the currently authenticated account",
    description=(
        "Returns the Account behind the current access token, plus its "
        "linked Owner embedded in full, if any. Account and Owner are "
        "separate identities linked only by id — `owner` is null when no "
        "Owner has been linked yet via `owner_id` at registration time."
    ),
    responses={
        401: {
            "description": (
                "Missing, invalid, expired, or malformed access token, or "
                "the account behind it no longer exists."
            )
        },
    },
)
async def get_me(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> AccountMeResponse:
    return await _build_account_me_response(session, account)


@router.post(
    "/me/link-owner",
    response_model=AccountMeResponse,
    summary="Link an existing Owner to the currently authenticated account",
    description=(
        "Self-service linking for an Account registered without an `owner_id` "
        "(or that never received one): looks up an Owner by NIF/NIE and links "
        "it to the current Account. Only links to an already-existing Owner — "
        "it never creates one; use `POST /owners` for that. An Account can "
        "link at most once — this cannot be used to change an already-linked "
        "Owner. No identity verification beyond knowing the NIF is performed: "
        "whoever supplies a given NIF first claims it, a deliberate, "
        "accepted trade-off pending a future invitation/verification flow."
    ),
    responses={
        401: {"description": "Missing, invalid, or expired access token."},
        409: {
            "description": (
                "Either this account already has a linked owner, or the "
                "supplied NIF could not be linked (identical response body "
                "whether the NIF matches no Owner at all or matches an Owner "
                "already linked to a different account — deliberately, to "
                "avoid letting a caller learn whether a given NIF is "
                "registered in Vecinio)."
            )
        },
        412: {"description": "The account was modified concurrently."},
        422: {"description": "Request body failed validation."},
    },
)
async def link_owner(
    request: LinkOwnerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> AccountMeResponse:
    account_repository = PostgresAccountRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    use_case = LinkOwnerToAccount(account_repository, owner_repository)

    await use_case.execute(account_id=account.id.value, nif=request.nif)

    linked_account = await account_repository.get_by_id(account.id)
    if linked_account is None:
        raise RuntimeError(
            f"Account {account.id.value} was not found immediately after "
            "linking an owner"
        )

    return await _build_account_me_response(session, linked_account)
