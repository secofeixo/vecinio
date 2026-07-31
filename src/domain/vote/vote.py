from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.community.value_objects import CommunityId
from src.domain.identity.value_objects import AccountId

from .value_objects import VoteId
from .vote_option import VoteOption
from .vote_result import VoteResult

_MINIMUM_OPTIONS = 2


class VoteDomainError(Exception):
    pass


class EmptyVoteTitleError(VoteDomainError):
    pass


class InsufficientVoteOptionsError(VoteDomainError):
    pass


class DuplicateVoteOptionLabelError(VoteDomainError):
    pass


class VoteEndDateNotInFutureError(VoteDomainError):
    pass


class VoteAlreadyClosedError(VoteDomainError):
    pass


class Vote(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: VoteId
    community_id: CommunityId
    title: str
    description: str
    options: tuple[VoteOption, ...] = Field(frozen=True)
    end_date: datetime
    created_by_account_id: AccountId
    result: VoteResult | None = None
    version: int = 0

    @model_validator(mode="after")
    def _check_invariants(self) -> Vote:
        self._check_title_is_valid(self.title)
        self._check_options_are_valid(self.options)
        return self

    @classmethod
    def create(
        cls,
        *,
        id: VoteId,
        community_id: CommunityId,
        title: str,
        description: str,
        options: tuple[VoteOption, ...],
        end_date: datetime,
        created_by_account_id: AccountId,
        now: datetime,
    ) -> Vote:
        cls._check_end_date_is_in_future(end_date, now)
        return cls(
            id=id,
            community_id=community_id,
            title=title,
            description=description,
            options=options,
            end_date=end_date,
            created_by_account_id=created_by_account_id,
        )

    @staticmethod
    def _check_title_is_valid(title: str) -> None:
        if not title.strip():
            raise EmptyVoteTitleError("Vote title must not be empty")

    @staticmethod
    def _check_options_are_valid(options: tuple[VoteOption, ...]) -> None:
        if len(options) < _MINIMUM_OPTIONS:
            raise InsufficientVoteOptionsError(
                f"A vote must have at least {_MINIMUM_OPTIONS} options"
            )
        labels = [option.label for option in options]
        if len(labels) != len(set(labels)):
            raise DuplicateVoteOptionLabelError(
                "Vote option labels must be unique within a vote"
            )

    @staticmethod
    def _check_end_date_is_in_future(end_date: datetime, now: datetime) -> None:
        if end_date <= now:
            raise VoteEndDateNotInFutureError(
                f"end_date {end_date} must be strictly after now ({now})"
            )

    def close(self, result: VoteResult) -> None:
        if self.result is not None:
            raise VoteAlreadyClosedError(f"Vote {self.id} has already been closed")
        self.result = result
