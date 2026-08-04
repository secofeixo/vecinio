from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.application.community.assign_owner_to_unit import (
    CommunityNotFoundError,
    OwnerNotFoundError,
)
from src.application.community_group.add_community_to_group import (
    CommunityGroupNotFoundError as AddCommunityGroupNotFoundError,
)
from src.application.community_group.add_community_to_group import (
    CommunityNotFoundError as AddCommunityGroupCommunityNotFoundError,
)
from src.application.community_group.create_community_group import (
    CommunityNotFoundError as CreateCommunityGroupCommunityNotFoundError,
)
from src.application.community_group.remove_community_from_group import (
    CommunityGroupNotFoundError as RemoveCommunityGroupNotFoundError,
)
from src.application.identity.login import InvalidCredentialsError
from src.application.identity.refresh_access_token import InvalidRefreshTokenError
from src.application.identity.register_account import (
    OwnerNotFoundError as AccountOwnerNotFoundError,
)
from src.application.quota.create_quota import (
    CommunityNotFoundError as CreateQuotaCommunityNotFoundError,
)
from src.application.quota.create_quota import (
    OverlappingOrdinaryQuotaError,
    QuotaNotFoundError,
)
from src.application.vote.cast_ballot import AccountNotAuthorizedToCastBallotError
from src.application.vote.cast_ballot import (
    AccountNotFoundError as CastBallotAccountNotFoundError,
)
from src.application.vote.cast_ballot import (
    CommunityNotFoundError as CastBallotCommunityNotFoundError,
)
from src.application.vote.cast_ballot import (
    OptionDoesNotBelongToVoteError,
    UnitAlreadyVotedByAnotherOwnerError,
    UnitNotFoundInCommunityError,
)
from src.application.vote.cast_ballot import (
    VoteHasEndedError as CastBallotHasEndedError,
)
from src.application.vote.cast_ballot import (
    VoteNotFoundError as CastBallotVoteNotFoundError,
)
from src.application.vote.close_vote import AccountNotAuthorizedToCloseVoteError
from src.application.vote.close_vote import (
    AccountNotFoundError as CloseVoteAccountNotFoundError,
)
from src.application.vote.close_vote import (
    CommunityNotFoundError as CloseVoteCommunityNotFoundError,
)
from src.application.vote.close_vote import VoteHasNotEndedYetError
from src.application.vote.close_vote import (
    VoteNotFoundError as CloseVoteVoteNotFoundError,
)
from src.application.vote.create_vote import AccountNotAuthorizedToCreateVoteError
from src.application.vote.create_vote import (
    AccountNotFoundError as CreateVoteAccountNotFoundError,
)
from src.application.vote.create_vote import (
    CommunityNotFoundError as CreateVoteCommunityNotFoundError,
)
from src.domain.community.community import (
    ConcurrentModificationError as CommunityConcurrentModificationError,
)
from src.domain.community.community import (
    DuplicateCifError,
    DuplicateUnitIdentifierError,
    OwnerAlreadyAssignedError,
    ParticipationCoefficientSumError,
    UnitNotFoundError,
)
from src.domain.community_group.community_group import (
    CommunityAlreadyMemberError,
    CommunityGroupBelowMinimumMembersError,
)
from src.domain.community_group.community_group import (
    CommunityNotMemberError as CommunityGroupCommunityNotMemberError,
)
from src.domain.community_group.community_group import (
    ConcurrentModificationError as CommunityGroupConcurrentModificationError,
)
from src.domain.community_group.community_group import (
    DuplicateCommunityGroupSlugError,
    InvalidCommunityGroupNameError,
)
from src.domain.identity.account import (
    ConcurrentModificationError as AccountConcurrentModificationError,
)
from src.domain.identity.account import DuplicateEmailError
from src.domain.owner.owner import (
    ConcurrentModificationError as OwnerConcurrentModificationError,
)
from src.domain.owner.owner import DuplicateNifError
from src.domain.quota.quota import (
    ConcurrentModificationError as QuotaConcurrentModificationError,
)
from src.domain.quota.quota import (
    EmptyQuotaAllocationsError,
    EmptyQuotaLinesError,
    InvalidQuotaPeriodError,
    InvalidQuotaTotalError,
)
from src.domain.vote.ballot import ConcurrentBallotSubmissionError
from src.domain.vote.vote import (
    ConcurrentModificationError as VoteConcurrentModificationError,
)
from src.domain.vote.vote import (
    DuplicateVoteOptionLabelError,
    EmptyVoteTitleError,
    InsufficientVoteOptionsError,
    VoteAlreadyClosedError,
    VoteEndDateNotInFutureError,
)
from src.interfaces.api.routers.owners import OwnerNotLinkedToAccountError

logger = logging.getLogger(__name__)


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


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(401, exc)


async def _handle_vote_community_access_denied(
    request: Request, exc: Exception
) -> JSONResponse:
    # Deliberately ignores str(exc): CommunityNotFoundError and
    # AccountNotAuthorizedToCreateVoteError must return byte-identical
    # responses, so a caller can never distinguish "no such community" from
    # "you don't own a unit there" and enumerate community existence.
    return JSONResponse(
        status_code=404,
        content={"detail": "Community not found or you are not a member of it"},
    )


async def _handle_vote_not_found(request: Request, exc: Exception) -> JSONResponse:
    # Deliberately ignores str(exc) (which includes the vote_id) in favor of
    # a fixed message. Shared by CastBallot's and CloseVote's VoteNotFoundError
    # -- both mean exactly the same thing ("no such vote") and should return
    # byte-identical bodies.
    return JSONResponse(status_code=404, content={"detail": "Vote not found"})


async def _handle_cast_ballot_not_authorized(
    request: Request, exc: Exception
) -> JSONResponse:
    # Deliberately ignores str(exc): AccountNotAuthorizedToCastBallotError
    # covers two distinct causes (account has no linked owner, or its owner
    # doesn't own the unit) that must return a byte-identical response so a
    # caller can't tell them apart. Kept separate from
    # OptionDoesNotBelongToVoteError and UnitNotFoundInCommunityError, which
    # keep their own distinct messages -- unit_id is treated as less
    # sensitive than community_id here, unlike CreateVote.
    return JSONResponse(
        status_code=404,
        content={"detail": "Not authorized to cast a ballot for this unit"},
    )


async def _handle_vote_persisted_community_not_found(
    request: Request, exc: Exception
) -> JSONResponse:
    # Theoretical only: a persisted Vote pointing at a Community that no
    # longer exists. Communities are never deleted, so no known code path
    # reaches this -- logged as an alert rather than silently 500ing, and not
    # exercised by an automated test. Shared by CastBallot's and CloseVote's
    # CommunityNotFoundError -- same theoretical scenario, same handling.
    # KNOWN GAP (pending, not resolved here): this codebase has no logging
    # configuration anywhere (no basicConfig/dictConfig, no handler, no
    # formatter, no level) -- this call relies on Python's logging.lastResort
    # fallback (unformatted, timestamp-less stderr output for WARNING+),
    # not on any real alerting/observability setup. Do not treat this as a
    # guarantee that an alert will actually be seen.
    logger.error("Vote references a community that could not be found: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


async def _handle_close_vote_not_authorized(
    request: Request, exc: Exception
) -> JSONResponse:
    # Deliberately ignores str(exc): AccountNotAuthorizedToCloseVoteError
    # covers two distinct causes (account has no linked owner, or its owner
    # doesn't own any unit in the vote's community) that must return a
    # byte-identical response so a caller can't tell them apart. Distinct
    # wording from CastBallot's unified message on purpose -- that one is
    # about a specific unit, this one is about closing the vote itself.
    return JSONResponse(
        status_code=404,
        content={"detail": "Not authorized to close this vote"},
    )


async def _handle_vote_already_closed(request: Request, exc: Exception) -> JSONResponse:
    # Dedicated fixed-message handler, NOT the generic _handle_conflict:
    # VoteAlreadyClosedError is raised both by CloseVote.execute() (own
    # duplicate check, see close_vote.py) and by Vote.close() (the
    # aggregate's own guard), and their f-string messages differ in format
    # (one embeds a raw UUID, the other a VoteId's pydantic str()) --
    # str(exc) would make the HTTP response depend on which of the two raised
    # it. A fixed message avoids that coupling entirely.
    return JSONResponse(
        status_code=409,
        content={"detail": "Vote has already been closed"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CommunityNotFoundError, _handle_not_found)
    app.add_exception_handler(OwnerNotFoundError, _handle_not_found)
    app.add_exception_handler(UnitNotFoundError, _handle_not_found)
    app.add_exception_handler(AccountOwnerNotFoundError, _handle_not_found)
    app.add_exception_handler(AddCommunityGroupNotFoundError, _handle_not_found)
    app.add_exception_handler(
        AddCommunityGroupCommunityNotFoundError, _handle_not_found
    )
    app.add_exception_handler(
        CreateCommunityGroupCommunityNotFoundError, _handle_not_found
    )
    app.add_exception_handler(RemoveCommunityGroupNotFoundError, _handle_not_found)
    app.add_exception_handler(CommunityGroupCommunityNotMemberError, _handle_not_found)
    app.add_exception_handler(CreateQuotaCommunityNotFoundError, _handle_not_found)
    app.add_exception_handler(QuotaNotFoundError, _handle_not_found)
    app.add_exception_handler(OwnerNotLinkedToAccountError, _handle_not_found)

    app.add_exception_handler(DuplicateCifError, _handle_conflict)
    app.add_exception_handler(DuplicateNifError, _handle_conflict)
    app.add_exception_handler(OwnerAlreadyAssignedError, _handle_conflict)
    app.add_exception_handler(DuplicateEmailError, _handle_conflict)
    app.add_exception_handler(CommunityAlreadyMemberError, _handle_conflict)

    app.add_exception_handler(
        CommunityConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        OwnerConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        AccountConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        CommunityGroupConcurrentModificationError, _handle_concurrent_modification
    )
    app.add_exception_handler(
        QuotaConcurrentModificationError, _handle_concurrent_modification
    )

    app.add_exception_handler(InvalidCredentialsError, _handle_unauthorized)
    app.add_exception_handler(InvalidRefreshTokenError, _handle_unauthorized)
    app.add_exception_handler(CreateVoteAccountNotFoundError, _handle_unauthorized)

    app.add_exception_handler(
        CreateVoteCommunityNotFoundError, _handle_vote_community_access_denied
    )
    app.add_exception_handler(
        AccountNotAuthorizedToCreateVoteError, _handle_vote_community_access_denied
    )

    app.add_exception_handler(DuplicateUnitIdentifierError, _handle_value_error)
    app.add_exception_handler(ParticipationCoefficientSumError, _handle_value_error)
    app.add_exception_handler(DuplicateCommunityGroupSlugError, _handle_value_error)
    app.add_exception_handler(InvalidCommunityGroupNameError, _handle_value_error)
    app.add_exception_handler(
        CommunityGroupBelowMinimumMembersError, _handle_value_error
    )
    app.add_exception_handler(OverlappingOrdinaryQuotaError, _handle_value_error)
    app.add_exception_handler(EmptyQuotaLinesError, _handle_value_error)
    app.add_exception_handler(InvalidQuotaTotalError, _handle_value_error)
    app.add_exception_handler(EmptyQuotaAllocationsError, _handle_value_error)
    app.add_exception_handler(InvalidQuotaPeriodError, _handle_value_error)
    app.add_exception_handler(EmptyVoteTitleError, _handle_value_error)
    app.add_exception_handler(InsufficientVoteOptionsError, _handle_value_error)
    app.add_exception_handler(DuplicateVoteOptionLabelError, _handle_value_error)
    app.add_exception_handler(VoteEndDateNotInFutureError, _handle_value_error)
    app.add_exception_handler(ValueError, _handle_value_error)

    app.add_exception_handler(
        VoteConcurrentModificationError, _handle_concurrent_modification
    )

    app.add_exception_handler(CastBallotVoteNotFoundError, _handle_vote_not_found)
    app.add_exception_handler(CastBallotHasEndedError, _handle_conflict)
    app.add_exception_handler(CastBallotAccountNotFoundError, _handle_unauthorized)
    app.add_exception_handler(
        AccountNotAuthorizedToCastBallotError, _handle_cast_ballot_not_authorized
    )
    app.add_exception_handler(OptionDoesNotBelongToVoteError, _handle_not_found)
    app.add_exception_handler(
        CastBallotCommunityNotFoundError, _handle_vote_persisted_community_not_found
    )
    app.add_exception_handler(UnitNotFoundInCommunityError, _handle_not_found)
    app.add_exception_handler(UnitAlreadyVotedByAnotherOwnerError, _handle_conflict)
    app.add_exception_handler(ConcurrentBallotSubmissionError, _handle_conflict)

    app.add_exception_handler(CloseVoteVoteNotFoundError, _handle_vote_not_found)
    app.add_exception_handler(VoteAlreadyClosedError, _handle_vote_already_closed)
    app.add_exception_handler(VoteHasNotEndedYetError, _handle_conflict)
    app.add_exception_handler(CloseVoteAccountNotFoundError, _handle_unauthorized)
    app.add_exception_handler(
        AccountNotAuthorizedToCloseVoteError, _handle_close_vote_not_authorized
    )
    app.add_exception_handler(
        CloseVoteCommunityNotFoundError, _handle_vote_persisted_community_not_found
    )
