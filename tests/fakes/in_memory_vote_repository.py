from __future__ import annotations

from src.domain.vote.repository import VoteRepository
from src.domain.vote.value_objects import VoteId
from src.domain.vote.vote import Vote


class InMemoryVoteRepository(VoteRepository):
    def __init__(self) -> None:
        self._votes: dict[VoteId, Vote] = {}

    async def save(self, vote: Vote) -> None:
        self._votes[vote.id] = vote

    async def get_by_id(self, vote_id: VoteId) -> Vote | None:
        return self._votes.get(vote_id)

    def all(self) -> tuple[Vote, ...]:
        return tuple(self._votes.values())
