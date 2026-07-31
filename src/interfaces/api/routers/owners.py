from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.owner.register_owner import RegisterOwner
from src.domain.identity.account import Account
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.owner_schemas import CreateOwnerRequest, OwnerResponse

router = APIRouter(prefix="/owners", tags=["owner"])


@router.post(
    "",
    response_model=OwnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new owner",
    description=(
        "Creates an Owner — an independent legal/business identity (NIF/NIE, "
        "full name, contact info) that is not itself a login credential and "
        "can belong to zero or more communities. NIF/NIE are validated against "
        "the real Spanish checksum algorithms."
    ),
    responses={
        409: {"description": "An owner with this NIF/NIE already exists."},
        422: {"description": "Request body failed validation."},
    },
)
async def register_owner(
    request: CreateOwnerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> OwnerResponse:
    repository = PostgresOwnerRepository(session)
    use_case = RegisterOwner(repository)

    owner_id = await use_case.execute(
        nif=request.nif,
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
    )

    owner = await repository.get_by_id(owner_id)
    if owner is None:
        raise RuntimeError(
            f"Owner {owner_id.value} was not found immediately after registration"
        )

    return OwnerResponse(
        id=owner.id.value,
        nif=owner.nif.value,
        full_name=owner.full_name,
        email=owner.email.value,
        phone=owner.phone.value if owner.phone is not None else None,
    )
