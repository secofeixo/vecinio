from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.community.value_objects import UnitId
from src.domain.owner.value_objects import OwnerId

from .value_objects import BallotId, VoteId, VoteOptionId
from .vote import VoteDomainError


class BallotAlreadySupersededError(VoteDomainError):
    pass


class BallotCannotSupersedeItselfError(VoteDomainError):
    pass


class ConcurrentBallotSubmissionError(VoteDomainError):
    pass


class Ballot(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: BallotId = Field(frozen=True)
    vote_id: VoteId = Field(frozen=True)
    unit_id: UnitId = Field(frozen=True)
    option_id: VoteOptionId = Field(frozen=True)
    cast_by_owner_id: OwnerId = Field(frozen=True)
    cast_at: datetime = Field(frozen=True)
    superseded_by_ballot_id: BallotId | None = None

    @classmethod
    def create(
        cls,
        *,
        id: BallotId,
        vote_id: VoteId,
        unit_id: UnitId,
        option_id: VoteOptionId,
        cast_by_owner_id: OwnerId,
        now: datetime,
    ) -> Ballot:
        return cls(
            id=id,
            vote_id=vote_id,
            unit_id=unit_id,
            option_id=option_id,
            cast_by_owner_id=cast_by_owner_id,
            cast_at=now,
            superseded_by_ballot_id=None,
        )

    def supersede(self, by: BallotId) -> None:
        if by == self.id:
            raise BallotCannotSupersedeItselfError("A ballot cannot supersede itself")
        if self.superseded_by_ballot_id is not None:
            raise BallotAlreadySupersededError(
                f"Ballot {self.id} has already been superseded"
            )
        self.superseded_by_ballot_id = by
