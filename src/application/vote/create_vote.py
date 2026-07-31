from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from src.domain.community.repository import CommunityRepository
from src.domain.community.value_objects import CommunityId
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId
from src.domain.vote.repository import VoteRepository
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import Vote
from src.domain.vote.vote_option import VoteOption


class AccountNotFoundError(Exception):
    pass


class CommunityNotFoundError(Exception):
    pass


class AccountNotAuthorizedToCreateVoteError(Exception):
    pass


class CreateVote:
    def __init__(
        self,
        vote_repository: VoteRepository,
        account_repository: AccountRepository,
        community_repository: CommunityRepository,
    ) -> None:
        self._vote_repository = vote_repository
        self._account_repository = account_repository
        self._community_repository = community_repository

    async def execute(
        self,
        *,
        community_id: UUID,
        account_id: UUID,
        title: str,
        description: str,
        option_labels: Iterable[str],
        end_date: datetime,
        now: datetime,
    ) -> VoteId:
        account_id_vo = AccountId(value=account_id)
        account = await self._account_repository.get_by_id(account_id_vo)
        if account is None:
            raise AccountNotFoundError(f"No account found with id {account_id}")

        if account.owner_id is None:
            raise AccountNotAuthorizedToCreateVoteError(
                f"Account {account_id} has no linked owner and cannot create votes"
            )

        community_id_vo = CommunityId(value=community_id)
        community = await self._community_repository.get_by_id(community_id_vo)
        if community is None:
            raise CommunityNotFoundError(f"No community found with id {community_id}")

        owns_a_unit = any(
            account.owner_id in unit.owner_ids for unit in community.units
        )
        if not owns_a_unit:
            raise AccountNotAuthorizedToCreateVoteError(
                f"Account {account_id} does not own a unit in community {community_id}"
            )

        options = tuple(
            VoteOption(id=VoteOptionId.generate(), label=label)
            for label in option_labels
        )

        vote = Vote.create(
            id=VoteId.generate(),
            community_id=community_id_vo,
            title=title,
            description=description,
            options=options,
            end_date=end_date,
            created_by_account_id=account_id_vo,
            now=now,
        )

        await self._vote_repository.save(vote)
        return vote.id
