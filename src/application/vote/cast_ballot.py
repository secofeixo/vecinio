from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import UnitId
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId
from src.domain.vote.ballot import Ballot
from src.domain.vote.repository import BallotRepository, VoteRepository
from src.domain.vote.value_objects import BallotId, VoteId, VoteOptionId


class VoteNotFoundError(Exception):
    pass


class VoteHasEndedError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class AccountNotAuthorizedToCastBallotError(Exception):
    pass


class OptionDoesNotBelongToVoteError(Exception):
    pass


class CommunityNotFoundError(Exception):
    pass


class UnitNotFoundInCommunityError(Exception):
    pass


class UnitAlreadyVotedByAnotherOwnerError(Exception):
    pass


class CastBallot:
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
        unit_id: UUID,
        option_id: UUID,
        account_id: UUID,
        now: datetime,
    ) -> BallotId:
        vote_id_vo = VoteId(value=vote_id)
        vote = await self._vote_repository.get_by_id(vote_id_vo)
        if vote is None:
            raise VoteNotFoundError(f"No vote found with id {vote_id}")

        if now > vote.end_date:
            raise VoteHasEndedError(f"Vote {vote_id} ended at {vote.end_date}")

        account_id_vo = AccountId(value=account_id)
        account = await self._account_repository.get_by_id(account_id_vo)
        if account is None:
            raise AccountNotFoundError(f"No account found with id {account_id}")

        if account.owner_id is None:
            raise AccountNotAuthorizedToCastBallotError(
                f"Account {account_id} has no linked owner and cannot cast ballots"
            )

        option_id_vo = VoteOptionId(value=option_id)
        if not any(option.id == option_id_vo for option in vote.options):
            raise OptionDoesNotBelongToVoteError(
                f"Option {option_id} does not belong to vote {vote_id}"
            )

        community = await self._community_repository.get_by_id(vote.community_id)
        if community is None:
            raise CommunityNotFoundError(
                f"No community found with id {vote.community_id.value}"
            )

        unit_id_vo = UnitId(value=unit_id)
        unit = next((u for u in community.units if u.id == unit_id_vo), None)
        if unit is None:
            raise UnitNotFoundInCommunityError(
                f"No unit found with id {unit_id} in community {vote.community_id.value}"
            )

        if account.owner_id not in unit.owner_ids:
            raise AccountNotAuthorizedToCastBallotError(
                f"Account {account_id} does not own unit {unit_id}"
            )

        # TODO(race-condition): there is a real race window between
        # get_active_ballot and save() below — two concurrent requests (same
        # owner or two different owners) could both observe "no active
        # ballot" and each create a new active ballot for the same unit.
        # Accepted for now, same as the non-unique index accepted for Quota
        # overlap checks; will be closed by a DB-level partial UNIQUE
        # constraint on (vote_id, unit_id) WHERE superseded_by_ballot_id IS
        # NULL (infrastructure, pending).
        # The partial UNIQUE index now exists (ix_ballots_active_per_vote_unit)
        # and PostgresBallotRepository.save() translates its violation into
        # ConcurrentBallotSubmissionError — this use case could catch that and
        # retry (re-read the now-active ballot and supersede/reject) instead of
        # letting the race silently create two active ballots. Not done here;
        # left for the application-layer follow-up.
        existing_ballot = await self._ballot_repository.get_active_ballot(
            vote_id_vo, unit_id_vo
        )

        if existing_ballot is None:
            new_ballot = Ballot.create(
                id=BallotId.generate(),
                vote_id=vote_id_vo,
                unit_id=unit_id_vo,
                option_id=option_id_vo,
                cast_by_owner_id=account.owner_id,
                now=now,
            )
            await self._ballot_repository.save(new_ballot)
            return new_ballot.id

        if existing_ballot.cast_by_owner_id != account.owner_id:
            raise UnitAlreadyVotedByAnotherOwnerError(
                f"Unit {unit_id} already has a ballot cast by another owner"
            )

        new_ballot = Ballot.create(
            id=BallotId.generate(),
            vote_id=vote_id_vo,
            unit_id=unit_id_vo,
            option_id=option_id_vo,
            cast_by_owner_id=account.owner_id,
            now=now,
        )
        existing_ballot.supersede(new_ballot.id)
        await self._ballot_repository.save(existing_ballot)
        await self._ballot_repository.save(new_ballot)
        return new_ballot.id
