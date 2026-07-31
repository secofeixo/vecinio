from __future__ import annotations

from collections.abc import Sequence

from src.domain.community.value_objects import UnitId
from src.domain.vote.ballot import Ballot
from src.domain.vote.repository import BallotRepository
from src.domain.vote.value_objects import BallotId, VoteId


class InMemoryBallotRepository(BallotRepository):
    def __init__(self) -> None:
        self._ballots: dict[BallotId, Ballot] = {}

    async def save(self, ballot: Ballot) -> None:
        self._ballots[ballot.id] = ballot

    async def get_active_ballot(
        self, vote_id: VoteId, unit_id: UnitId
    ) -> Ballot | None:
        return next(
            (
                ballot
                for ballot in self._ballots.values()
                if ballot.vote_id == vote_id
                and ballot.unit_id == unit_id
                and ballot.superseded_by_ballot_id is None
            ),
            None,
        )

    async def get_all_active_for_vote(self, vote_id: VoteId) -> Sequence[Ballot]:
        return tuple(
            ballot
            for ballot in self._ballots.values()
            if ballot.vote_id == vote_id and ballot.superseded_by_ballot_id is None
        )

    def all(self) -> tuple[Ballot, ...]:
        return tuple(self._ballots.values())
