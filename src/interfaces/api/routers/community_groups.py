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

router = APIRouter(prefix="/community-groups", tags=["community_group"])


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
    "",
    response_model=CommunityGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a community group (mancomunidad)",
    description=(
        "Creates a CommunityGroup — the Spanish legal figure 'mancomunidad de "
        "propietarios' — referencing existing Community aggregates by id "
        "(it does not contain them; each Community keeps its own 100%-"
        "coefficient invariant independently). Requires at least 2 member "
        "communities. `slug` is derived automatically from `name` and is never "
        "a settable input. A Community may belong to more than one group at "
        "the same time — there is no membership-exclusivity invariant."
    ),
    responses={
        404: {"description": "One of the given community ids does not exist."},
        400: {
            "description": (
                "Fewer than 2 community ids were given, `name` is empty or "
                "normalizes to an empty slug, or the derived slug collides with "
                "an existing community group."
            )
        },
        422: {"description": "Request body failed validation."},
    },
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
    "/{group_id}/communities/{community_id}",
    response_model=CommunityGroupResponse,
    summary="Add a community to a group",
    description=(
        "Adds an existing Community as a member of the group. Membership "
        "rules (no duplicates, minimum of 2 members) are enforced on every "
        "mutation, not just at creation."
    ),
    responses={
        404: {
            "description": "The group does not exist, or the community does not exist."
        },
        409: {"description": "The community is already a member of this group."},
        412: {
            "description": (
                "The group was concurrently modified since it was last read "
                "(optimistic concurrency version conflict)."
            )
        },
        422: {"description": "`group_id` or `community_id` is not a valid UUID."},
    },
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
    "/{group_id}/communities/{community_id}",
    response_model=CommunityGroupResponse,
    summary="Remove a community from a group",
    description=(
        "Removes a Community from a group's membership. A group must keep at "
        "least 2 members at all times — removing one when only 2 remain is "
        "rejected."
    ),
    responses={
        404: {
            "description": (
                "The group does not exist, or the community is not currently a "
                "member of it."
            )
        },
        400: {
            "description": (
                "Removing this member would leave the group with fewer than 2 "
                "members."
            )
        },
        412: {
            "description": (
                "The group was concurrently modified since it was last read "
                "(optimistic concurrency version conflict)."
            )
        },
        422: {"description": "`group_id` or `community_id` is not a valid UUID."},
    },
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
