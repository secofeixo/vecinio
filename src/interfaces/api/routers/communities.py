from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.community.assign_owner_to_unit import (
    AssignOwnerToUnit,
    CommunityNotFoundError,
)
from src.application.community.register_community import RegisterCommunity, UnitInput
from src.domain.community.community import Community
from src.domain.community.value_objects import CommunityId
from src.domain.identity.account import Account
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.owner_repository import PostgresOwnerRepository
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.community_schemas import (
    AddressResponse,
    AssignOwnerToUnitRequest,
    CommunityResponse,
    CreateCommunityRequest,
    UnitResponse,
)

router = APIRouter(prefix="/communities", tags=["communities"])


def _to_response(community: Community) -> CommunityResponse:
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
                identifier=unit.identifier,
                participation_coefficient=unit.participation_coefficient.value,
                owner_ids=[owner_id.value for owner_id in unit.owner_ids],
            )
            for unit in community.units
        ],
    )


@router.post("", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
async def create_community(
    request: CreateCommunityRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
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
                identifier=unit.identifier,
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

    return _to_response(community)


@router.get("/{community_id}", response_model=CommunityResponse)
async def get_community(
    community_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> CommunityResponse:
    repository = PostgresCommunityRepository(session)

    community = await repository.get_by_id(CommunityId(value=community_id))
    if community is None:
        raise CommunityNotFoundError(f"No community found with id {community_id}")

    return _to_response(community)


@router.post("/{community_id}/units/{unit_id}/owners", response_model=CommunityResponse)
async def assign_owner_to_unit(
    community_id: UUID,
    unit_id: UUID,
    request: AssignOwnerToUnitRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> CommunityResponse:
    community_repository = PostgresCommunityRepository(session)
    owner_repository = PostgresOwnerRepository(session)
    use_case = AssignOwnerToUnit(community_repository, owner_repository)

    await use_case.execute(
        community_id=community_id,
        unit_id=unit_id,
        owner_id=request.owner_id,
    )

    community = await community_repository.get_by_id(CommunityId(value=community_id))
    if community is None:
        raise RuntimeError(
            f"Community {community_id} was not found immediately after "
            "assigning owner to unit"
        )

    return _to_response(community)
