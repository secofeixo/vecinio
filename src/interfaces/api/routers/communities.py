from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.community.register_community import RegisterCommunity, UnitInput
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.interfaces.api.dependencies import get_session
from src.interfaces.api.schemas.community_schemas import (
    AddressResponse,
    CommunityResponse,
    CreateCommunityRequest,
    UnitResponse,
)

router = APIRouter(prefix="/communities", tags=["communities"])


@router.post("", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
async def create_community(
    request: CreateCommunityRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> CommunityResponse:
    repository = PostgresCommunityRepository(session)
    use_case = RegisterCommunity(repository)

    community_id = await use_case.execute(
        name=request.name,
        street=request.street,
        number=request.number,
        city=request.city,
        postal_code=request.postal_code,
        province=request.province,
        cif=request.cif,
        units=[
            UnitInput(
                participation_coefficient=unit.participation_coefficient,
                unit_id=unit.unit_id,
                owner_ids=tuple(unit.owner_ids),
            )
            for unit in request.units
        ],
    )

    community = await repository.get_by_id(community_id)
    if community is None:
        raise RuntimeError(
            f"Community {community_id.value} was not found immediately after "
            "registration"
        )

    return CommunityResponse(
        id=community.id.value,
        name=community.name,
        address=AddressResponse(
            street=community.address.street,
            number=community.address.number,
            city=community.address.city,
            postal_code=community.address.postal_code,
            province=community.address.province,
        ),
        cif=community.cif.value,
        units=[
            UnitResponse(
                id=unit.id.value,
                participation_coefficient=unit.participation_coefficient.value,
                owner_ids=[owner_id.value for owner_id in unit.owner_ids],
            )
            for unit in community.units
        ],
    )
