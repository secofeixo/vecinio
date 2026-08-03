from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.vote.cast_ballot import CastBallot
from src.application.vote.close_vote import CloseVote
from src.application.vote.create_vote import CreateVote
from src.domain.identity.account import Account
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.vote_repository import (
    PostgresBallotRepository,
    PostgresVoteRepository,
)
from src.interfaces.api.dependencies import get_current_account, get_session
from src.interfaces.api.schemas.vote_schemas import (
    CastBallotRequest,
    CastBallotResponse,
    CloseVoteResponse,
    CreateVoteRequest,
    CreateVoteResponse,
    OptionTallyResponse,
)

router = APIRouter(prefix="/communities/{community_id}/votes", tags=["vote"])

# Deliberately a separate router, not nested under /communities/{community_id}:
# CastBallot never receives or needs a community_id -- it derives the
# community from the vote itself.
ballot_router = APIRouter(prefix="/votes", tags=["vote"])


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


@ballot_router.post(
    "/{vote_id}/ballots",
    response_model=CastBallotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast or correct a ballot for a vote",
    description=(
        "Casts a ballot for a Unit in an open vote. If the Unit already has "
        "an active ballot cast by the SAME owner, this corrects (supersedes) "
        "it instead of creating a second one -- a different co-owner of the "
        "same Unit cannot override an existing ballot. The authenticated "
        "account must be linked to an Owner who owns the target Unit. Ballot "
        "content (which option was chosen) is secret until the vote is "
        "closed; only the fact that the Unit has voted is visible before "
        "then."
    ),
    responses={
        401: {
            "description": (
                "The authenticated account could not be found. Defense in "
                "depth only -- not reachable in practice, since "
                "get_current_account already rejects unknown accounts."
            )
        },
        404: {
            "description": (
                "No vote exists with the given id; OR the account is not "
                "authorized to cast a ballot for this unit (no linked owner, "
                "or its owner does not own the unit -- unified deliberately "
                "into a single message so a caller cannot tell the two "
                "causes apart); OR `option_id` does not belong to this "
                "vote's options; OR `unit_id` does not exist in the vote's "
                "community. Each case has its own distinct message except "
                "the authorization one, which is intentionally unified."
            )
        },
        409: {
            "description": (
                "The vote has already ended (`end_date` is in the past); OR "
                "the unit already has an active ballot cast by a different "
                "owner; OR a concurrent request raced this one for the same "
                "vote/unit pair (partial UNIQUE constraint)."
            )
        },
        422: {"description": "Request body failed validation."},
        500: {
            "description": (
                "Theoretical only: the vote points at a community that no "
                "longer exists. No known code path reaches this -- "
                "communities are never deleted -- logged as an alert if it "
                "ever occurs."
            )
        },
    },
)
async def cast_ballot(
    vote_id: UUID,
    request: CastBallotRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> CastBallotResponse:
    vote_repository = PostgresVoteRepository(session)
    ballot_repository = PostgresBallotRepository(session)
    account_repository = PostgresAccountRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = CastBallot(
        vote_repository, ballot_repository, account_repository, community_repository
    )

    ballot_id = await use_case.execute(
        vote_id=vote_id,
        unit_id=request.unit_id,
        option_id=request.option_id,
        account_id=account.id.value,
        now=datetime.now(timezone.utc),
    )

    return CastBallotResponse(ballot_id=ballot_id.value)


@ballot_router.post(
    "/{vote_id}/close",
    response_model=CloseVoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Close a vote and compute its result",
    description=(
        "Closes an open vote whose `end_date` has already passed and "
        "computes its final tallies -- raw counts only, unit-count basis AND "
        "coefficient-weighted basis, side by side, never an approved/rejected "
        "verdict. A vote can only be closed once. The authenticated account "
        "must be linked to an Owner who owns at least one Unit in the vote's "
        "community; this authorization is independent of who created the "
        "vote -- any qualifying owner may close it."
    ),
    responses={
        401: {
            "description": (
                "The authenticated account could not be found. Defense in "
                "depth only -- not reachable in practice, since "
                "get_current_account already rejects unknown accounts."
            )
        },
        404: {
            "description": (
                "No vote exists with the given id (`Vote not found`); OR the "
                "account is not authorized to close this vote (no linked "
                "owner, or its owner does not own a unit in the vote's "
                "community -- unified deliberately into a single message so "
                "a caller cannot tell the two causes apart)."
            )
        },
        409: {
            "description": (
                "The vote has already been closed; OR `end_date` has not "
                "passed yet. The already-closed check runs first, so a vote "
                "that is already closed always reports as such even in the "
                "edge case where `end_date` is still in the future."
            )
        },
        412: {
            "description": (
                "The vote was modified concurrently by another request "
                "(optimistic-concurrency version conflict) -- no automatic "
                "retry. NOT a closed design decision specific to this "
                "endpoint: a general strategy for handling 409/412 "
                "concurrency conflicts at the router level (retry? surface "
                "as-is? something else?) is pending across the whole "
                "project, not just CloseVote. Do not add retry logic here "
                "in isolation without discussing that broader strategy "
                "first."
            )
        },
        500: {
            "description": (
                "Theoretical only: the vote points at a community that no "
                "longer exists. No known code path reaches this -- "
                "communities are never deleted -- logged as an alert if it "
                "ever occurs."
            )
        },
    },
)
async def close_vote(
    vote_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    account: Account = Depends(get_current_account),  # noqa: B008
) -> CloseVoteResponse:
    vote_repository = PostgresVoteRepository(session)
    ballot_repository = PostgresBallotRepository(session)
    account_repository = PostgresAccountRepository(session)
    community_repository = PostgresCommunityRepository(session)
    use_case = CloseVote(
        vote_repository, ballot_repository, account_repository, community_repository
    )

    result = await use_case.execute(
        vote_id=vote_id,
        account_id=account.id.value,
        now=datetime.now(timezone.utc),
    )

    return CloseVoteResponse(
        tallies=[
            OptionTallyResponse(
                option_id=tally.option_id.value,
                unit_count=tally.unit_count,
                weighted_coefficient=tally.weighted_coefficient,
            )
            for tally in result.tallies
        ],
        total_units_in_community=result.total_units_in_community,
        units_that_voted=result.units_that_voted,
        total_participation_coefficient=result.total_participation_coefficient,
        closed_at=result.closed_at,
    )
