from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.community.value_objects import UnitId

from .ballot import Ballot
from .value_objects import VoteId
from .vote import Vote


class VoteRepository(ABC):
    @abstractmethod
    async def save(self, vote: Vote) -> None: ...

    @abstractmethod
    async def get_by_id(self, vote_id: VoteId) -> Vote | None: ...


class BallotRepository(ABC):
    @abstractmethod
    async def save(self, ballot: Ballot) -> None: ...

    @abstractmethod
    async def get_active_ballot(
        self, vote_id: VoteId, unit_id: UnitId
    ) -> Ballot | None: ...
