from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.application.community.assign_owner_to_unit import (
    CommunityNotFoundError,
    OwnerNotFoundError,
)
from src.domain.community.community import (
    ConcurrentModificationError as CommunityConcurrentModificationError,
)
from src.domain.community.community import (
    DuplicateCifError,
    OwnerAlreadyAssignedError,
    UnitNotFoundError,
)
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


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CommunityNotFoundError, _handle_not_found)
    app.add_exception_handler(OwnerNotFoundError, _handle_not_found)
    app.add_exception_handler(UnitNotFoundError, _handle_not_found)

    app.add_exception_handler(DuplicateCifError, _handle_conflict)
    app.add_exception_handler(DuplicateNifError, _handle_conflict)
    app.add_exception_handler(OwnerAlreadyAssignedError, _handle_conflict)

    app.add_exception_handler(
        CommunityConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        OwnerConcurrentModificationError, _handle_concurrent_modification
    )

    app.add_exception_handler(ValueError, _handle_value_error)
