from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.domain.community.value_objects import CommunityId, UnitId

from .ballot import Ballot
from .value_objects import VoteId
from .vote import Vote


class VoteRepository(ABC):
    @abstractmethod
    async def save(self, vote: Vote) -> None: ...

    @abstractmethod
    async def get_by_id(self, vote_id: VoteId) -> Vote | None: ...

    @abstractmethod
    async def exists_open_vote_for_community(
        self, community_id: CommunityId
    ) -> bool: ...


class BallotRepository(ABC):
    @abstractmethod
    async def save(self, ballot: Ballot) -> None: ...

    @abstractmethod
    async def get_active_ballot(
        self, vote_id: VoteId, unit_id: UnitId
    ) -> Ballot | None: ...

    @abstractmethod
    async def get_all_active_for_vote(self, vote_id: VoteId) -> Sequence[Ballot]: ...
