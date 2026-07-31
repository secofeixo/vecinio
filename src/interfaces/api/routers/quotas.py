from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.quota.create_quota import CreateQuota, QuotaNotFoundError
from src.domain.community.value_objects import CommunityId
from src.domain.identity.account import Account
from src.domain.quota.quota import Quota
from src.domain.quota.value_objects import QuotaId
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.quota_repository import PostgresQuotaRepository
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.quota_schemas import (
    CreateQuotaRequest,
    QuotaAllocationResponse,
    QuotaLineResponse,
    QuotaResponse,
)

router = APIRouter(prefix="/communities/{community_id}/quotas", tags=["quota"])


def _to_response(quota: Quota) -> QuotaResponse:
    return QuotaResponse(
        id=quota.id.value,
        community_id=quota.community_id.value,
        type=quota.type,
        period_start=quota.period_start,
        period_end=quota.period_end,
        lines=[
            QuotaLineResponse(concept=line.concept, amount=line.amount)
            for line in quota.lines
        ],
        total=quota.total,
        allocations=[
            QuotaAllocationResponse(
                unit_id=allocation.unit_id.value,
                participation_coefficient=allocation.participation_coefficient,
                amount=allocation.amount,
            )
            for allocation in quota.allocations
        ],
        supersedes_quota_id=(
            quota.supersedes_quota_id.value
            if quota.supersedes_quota_id is not None
            else None
        ),
        version=quota.version,
    )


@router.post(
    "",
    response_model=QuotaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quota for a community",
    description=(
        "Creates an immutable snapshot split of an amount across every Unit "
        "currently in the community, using the largest-remainder method so "
        "per-unit allocations always sum exactly to the total. `total` is "
        "computed from `lines`, never supplied directly. An ordinary quota's "
        "period must not overlap — inclusive on both bounds — another "
        "ordinary quota of the same community; extraordinary quotas are never "
        "checked for overlap against anything. This endpoint only covers "
        "creation: billing, payment tracking, periodicity, and quota "
        "recalculation/superseding are not implemented yet."
    ),
    responses={
        404: {"description": "No community exists with the given id."},
        400: {
            "description": (
                "The quota is invalid: an overlapping ordinary quota already "
                "exists for this community, `lines` is empty, the computed "
                "total is not strictly positive, `period_start` is after "
                "`period_end`, or the community has no units to allocate to."
            )
        },
        422: {"description": "Request body failed validation."},
    },
)
async def create_quota(
    community_id: UUID,
    request: CreateQuotaRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> QuotaResponse:
    quota_repository = PostgresQuotaRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = CreateQuota(quota_repository, community_repository)

    quota_id = await use_case.execute(
        community_id=community_id,
        type=request.type,
        period_start=request.period_start,
        period_end=request.period_end,
        lines=[(line.concept, line.amount) for line in request.lines],
    )

    quota = await quota_repository.get_by_id(quota_id)
    if quota is None:
        raise RuntimeError(
            f"Quota {quota_id.value} was not found immediately after creation"
        )

    return _to_response(quota)


@router.get(
    "/{quota_id}",
    response_model=QuotaResponse,
    summary="Get a quota by id",
    description=(
        "Returns the quota snapshot: lines, computed total, and the frozen "
        "per-unit allocations captured at creation time (never recalculated "
        "against current Unit state)."
    ),
    responses={
        404: {
            "description": "No quota exists with the given id within this community."
        },
        422: {"description": "`community_id` or `quota_id` is not a valid UUID."},
    },
)
async def get_quota(
    community_id: UUID,
    quota_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    _: Account = Depends(get_current_account),  # noqa: B008
) -> QuotaResponse:
    quota_repository = PostgresQuotaRepository(session)

    quota = await quota_repository.get_by_id(QuotaId(value=quota_id))
    if quota is None or quota.community_id != CommunityId(value=community_id):
        raise QuotaNotFoundError(f"No quota found with id {quota_id}")

    return _to_response(quota)
