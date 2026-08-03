from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.vote.create_vote import CreateVote
from src.domain.identity.account import Account
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.vote_repository import PostgresVoteRepository
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.vote_schemas import (
    CreateVoteRequest,
    CreateVoteResponse,
)

router = APIRouter(prefix="/communities/{community_id}/votes", tags=["vote"])


@router.post(
    "",
    response_model=CreateVoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a vote for a community",
    description=(
        "Opens a new consultation with two or more options, fixed at creation "
        "time (minimum 2, unique labels) — options can never be added to or "
        "removed afterwards. `end_date` must be strictly in the future at "
        "creation time. Only an account linked to an Owner who owns at least "
        "one Unit in the community may create a vote for it. The vote reports "
        "raw tallies only when later closed; it never computes an "
        "approved/rejected verdict."
    ),
    responses={
        400: {
            "description": (
                "The vote is invalid: `title` is empty, fewer than 2 options "
                "were supplied, two options share the same label, or "
                "`end_date` is not strictly in the future."
            )
        },
        401: {
            "description": (
                "The authenticated account could not be found. Defense in "
                "depth only — not reachable in practice, since "
                "get_current_account already rejects unknown accounts."
            )
        },
        404: {
            "description": (
                "No community exists with the given id, or the authenticated "
                "account does not own a unit in it. Both cases return the "
                "identical response body deliberately, so a caller cannot use "
                "this endpoint to enumerate which communities exist."
            )
        },
        412: {"description": "The vote was modified concurrently by another request."},
        422: {"description": "Request body failed validation."},
    },
)
async def create_vote(
    community_id: UUID,
    request: CreateVoteRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> CreateVoteResponse:
    vote_repository = PostgresVoteRepository(session)
    account_repository = PostgresAccountRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = CreateVote(vote_repository, account_repository, community_repository)

    vote_id = await use_case.execute(
        community_id=community_id,
        account_id=account.id.value,
        title=request.title,
        description=request.description,
        option_labels=request.option_labels,
        end_date=request.end_date,
        now=datetime.now(timezone.utc),
    )

    return CreateVoteResponse(vote_id=vote_id.value)
