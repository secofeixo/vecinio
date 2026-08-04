from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.owner.register_owner import RegisterOwner
from src.domain.identity.account import Account
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.community_schemas import AddressResponse
from src.interfaces.api.schemas.owner_schemas import (
    CreateOwnerRequest,
    OwnerResponse,
    OwnerUnitResponse,
)

router = APIRouter(prefix="/owners", tags=["owner"])


class OwnerNotLinkedToAccountError(Exception):
    pass


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


# NOTE: declared before any future GET /owners/{owner_id} — FastAPI matches
# path operations in declaration order, and {owner_id} would otherwise
# swallow "/me/units".
@router.get(
    "/me/units",
    response_model=list[OwnerUnitResponse],
    summary="List the units owned by the currently authenticated owner",
    description=(
        "Returns every Unit, across all Communities, whose owner_ids include "
        "the Owner linked to the current Account. Each item embeds its "
        "Community's id, name, and address, since no community-listing "
        "endpoint exists yet. Returns an empty list if the linked Owner owns "
        "no units."
    ),
    responses={
        404: {"description": "No owner is linked to this account."},
    },
)
async def get_my_units(
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> list[OwnerUnitResponse]:
    if account.owner_id is None:
        raise OwnerNotLinkedToAccountError("No owner is linked to this account")

    community_repository = PostgresCommunityRepository(session)
    communities = await community_repository.find_by_owner_id(account.owner_id)

    return [
        OwnerUnitResponse(
            id=unit.id.value,
            identifier=unit.identifier,
            participation_coefficient=unit.participation_coefficient.value,
            community_id=community.id.value,
            community_name=community.name,
            community_address=AddressResponse(
                street=community.address.street,
                number=community.address.number,
                city=community.address.city,
                postal_code=community.address.postal_code,
                province=community.address.province,
            ),
        )
        for community in communities
        for unit in community.units
        if account.owner_id in unit.owner_ids
    ]
