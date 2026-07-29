from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.application.community.assign_owner_to_unit import (
    CommunityNotFoundError,
    OwnerNotFoundError,
)
from src.application.identity.login import InvalidCredentialsError
from src.application.identity.refresh_access_token import InvalidRefreshTokenError
from src.application.identity.register_account import (
    OwnerNotFoundError as AccountOwnerNotFoundError,
)
from src.domain.community.community import (
    ConcurrentModificationError as CommunityConcurrentModificationError,
)
from src.domain.community.community import (
    DuplicateCifError,
    OwnerAlreadyAssignedError,
    UnitNotFoundError,
)
from src.domain.identity.account import (
    ConcurrentModificationError as AccountConcurrentModificationError,
)
from src.domain.identity.account import DuplicateEmailError
from src.domain.owner.owner import (
    ConcurrentModificationError as OwnerConcurrentModificationError,
)
from src.domain.owner.owner import DuplicateNifError


def _error_response(status_code: int, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(404, exc)


async def _handle_conflict(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(409, exc)


async def _handle_concurrent_modification(
    request: Request, exc: Exception
) -> JSONResponse:
    return _error_response(412, exc)


async def _handle_value_error(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(400, exc)


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(401, exc)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CommunityNotFoundError, _handle_not_found)
    app.add_exception_handler(OwnerNotFoundError, _handle_not_found)
    app.add_exception_handler(UnitNotFoundError, _handle_not_found)
    app.add_exception_handler(AccountOwnerNotFoundError, _handle_not_found)

    app.add_exception_handler(DuplicateCifError, _handle_conflict)
    app.add_exception_handler(DuplicateNifError, _handle_conflict)
    app.add_exception_handler(OwnerAlreadyAssignedError, _handle_conflict)
    app.add_exception_handler(DuplicateEmailError, _handle_conflict)

    app.add_exception_handler(
        CommunityConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        OwnerConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        AccountConcurrentModificationError, _handle_concurrent_modification
    )

    app.add_exception_handler(InvalidCredentialsError, _handle_unauthorized)
    app.add_exception_handler(InvalidRefreshTokenError, _handle_unauthorized)

    app.add_exception_handler(ValueError, _handle_value_error)
