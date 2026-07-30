from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.community_group.add_community_to_group import AddCommunityToGroup
from src.application.community_group.create_community_group import CreateCommunityGroup
from src.application.community_group.remove_community_from_group import (
    RemoveCommunityFromGroup,
)
from src.domain.community_group.community_group import CommunityGroup
from src.domain.identity.account import Account
from src.infrastructure.persistence.community_group_repository import (
    PostgresCommunityGroupRepository,
)
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.community_group_schemas import (
    CommunityGroupResponse,
    CreateCommunityGroupRequest,
)

router = APIRouter(prefix="/community-groups", tags=["community-groups"])


def _to_response(group: CommunityGroup) -> CommunityGroupResponse:
    return CommunityGroupResponse(
        id=group.id.value,
        name=group.name,
        slug=group.slug,
        member_community_ids=[
            community_id.value for community_id in group.member_community_ids
        ],
    )


@router.post(
    "", response_model=CommunityGroupResponse, status_code=status.HTTP_201_CREATED
)
async def create_community_group(
    request: CreateCommunityGroupRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> CommunityGroupResponse:
    group_repository = PostgresCommunityGroupRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = CreateCommunityGroup(group_repository, community_repository)

    group_id = await use_case.execute(
        name=request.name, community_ids=request.community_ids
    )

    group = await group_repository.get_by_id(group_id)
    if group is None:
        raise RuntimeError(
            f"CommunityGroup {group_id.value} was not found immediately after "
            "creation"
        )

    return _to_response(group)


@router.post(
    "/{group_id}/communities/{community_id}", response_model=CommunityGroupResponse
)
async def add_community_to_group(
    group_id: UUID,
    community_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> CommunityGroupResponse:
    group_repository = PostgresCommunityGroupRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = AddCommunityToGroup(group_repository, community_repository)

    group = await use_case.execute(group_id=group_id, community_id=community_id)

    return _to_response(group)


@router.delete(
    "/{group_id}/communities/{community_id}", response_model=CommunityGroupResponse
)
async def remove_community_from_group(
    group_id: UUID,
    community_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> CommunityGroupResponse:
    group_repository = PostgresCommunityGroupRepository(session)
    use_case = RemoveCommunityFromGroup(group_repository)

    group = await use_case.execute(group_id=group_id, community_id=community_id)

    return _to_response(group)
