from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId
from src.domain.vote.calculation import calculate_vote_result
from src.domain.vote.repository import BallotRepository, VoteRepository
from src.domain.vote.value_objects import VoteId
from src.domain.vote.vote import VoteAlreadyClosedError
from src.domain.vote.vote_result import VoteResult


class VoteNotFoundError(Exception):
    pass


class VoteHasNotEndedYetError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class AccountNotAuthorizedToCloseVoteError(Exception):
    pass


class CommunityNotFoundError(Exception):
    pass


class CloseVote:
    def __init__(
        self,
        vote_repository: VoteRepository,
        ballot_repository: BallotRepository,
        account_repository: AccountRepository,
        community_repository: CommunityRepository,
    ) -> None:
        self._vote_repository = vote_repository
        self._ballot_repository = ballot_repository
        self._account_repository = account_repository
        self._community_repository = community_repository

    async def execute(
        self,
        *,
        vote_id: UUID,
        account_id: UUID,
        now: datetime,
    ) -> VoteResult:
        vote_id_vo = VoteId(value=vote_id)
        vote = await self._vote_repository.get_by_id(vote_id_vo)
        if vote is None:
            raise VoteNotFoundError(f"No vote found with id {vote_id}")

        # Checked here, before the end_date check, so an already-closed vote
        # always surfaces as VoteAlreadyClosedError -- even in the edge case
        # (unreachable via normal HTTP flow, only via a repository bypass)
        # where end_date hasn't arrived yet. Vote.close() keeps its own
        # identical check below as the aggregate's own protection for any
        # other entry point -- deliberate duplication, not merged into one.
        if vote.result is not None:
            raise VoteAlreadyClosedError(f"Vote {vote_id} has already been closed")

        if not now > vote.end_date:
            raise VoteHasNotEndedYetError(
                f"Vote {vote_id} has not ended yet (end_date {vote.end_date})"
            )

        account_id_vo = AccountId(value=account_id)
        account = await self._account_repository.get_by_id(account_id_vo)
        if account is None:
            raise AccountNotFoundError(f"No account found with id {account_id}")

        if account.owner_id is None:
            raise AccountNotAuthorizedToCloseVoteError(
                f"Account {account_id} has no linked owner and cannot close votes"
            )

        community = await self._community_repository.get_by_id(vote.community_id)
        if community is None:
            raise CommunityNotFoundError(
                f"No community found with id {vote.community_id.value}"
            )

        owns_a_unit = any(
            account.owner_id in unit.owner_ids for unit in community.units
        )
        if not owns_a_unit:
            raise AccountNotAuthorizedToCloseVoteError(
                f"Account {account_id} does not own a unit in community "
                f"{vote.community_id.value}"
            )

        ballots = await self._ballot_repository.get_all_active_for_vote(vote_id_vo)

        result = calculate_vote_result(
            ballots=ballots,
            units=community.units,
            options=vote.options,
            now=now,
        )

        vote.close(result)
        await self._vote_repository.save(vote)
        return result
