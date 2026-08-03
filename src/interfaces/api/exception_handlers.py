from __future__ import annotations

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
from src.domain.vote.vote import (
    ConcurrentModificationError as VoteConcurrentModificationError,
)
from src.domain.vote.vote import (
    DuplicateVoteOptionLabelError,
    EmptyVoteTitleError,
    InsufficientVoteOptionsError,
    VoteEndDateNotInFutureError,
)


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
