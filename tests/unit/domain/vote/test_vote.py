from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.domain.community.value_objects import CommunityId
from src.domain.identity.value_objects import AccountId
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import (
    DuplicateVoteOptionLabelError,
    EmptyVoteTitleError,
    InsufficientVoteOptionsError,
    Vote,
    VoteEndDateNotInFutureError,
)
from src.domain.vote.vote_option import VoteOption

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_options(*labels: str) -> tuple[VoteOption, ...]:
    return tuple(
        VoteOption(id=VoteOptionId.generate(), label=label) for label in labels
    )


def make_vote(
    title: str = "Repair the roof",
    description: str = "",
    options: tuple[VoteOption, ...] | None = None,
    end_date: datetime | None = None,
    now: datetime = _NOW,
) -> Vote:
    return Vote.create(
        id=VoteId.generate(),
        community_id=CommunityId.generate(),
        title=title,
        description=description,
        options=options if options is not None else make_options("Yes", "No"),
        end_date=end_date if end_date is not None else _NOW + timedelta(days=7),
        created_by_account_id=AccountId.generate(),
        now=now,
    )


def test_creates_vote_with_valid_data() -> None:
    vote = make_vote()

    assert vote.title == "Repair the roof"
    assert len(vote.options) == 2
    assert vote.version == 0


def test_rejects_empty_title() -> None:
    with pytest.raises(EmptyVoteTitleError):
        make_vote(title="   ")


def test_accepts_empty_description() -> None:
    vote = make_vote(description="")

    assert vote.description == ""


def test_rejects_fewer_than_two_options() -> None:
    with pytest.raises(InsufficientVoteOptionsError):
        make_vote(options=make_options("Yes"))


def test_rejects_duplicate_option_labels() -> None:
    with pytest.raises(DuplicateVoteOptionLabelError):
        make_vote(options=make_options("Yes", "Yes"))


def test_rejects_end_date_not_in_future() -> None:
    with pytest.raises(VoteEndDateNotInFutureError):
        make_vote(end_date=_NOW, now=_NOW)


def test_rejects_end_date_in_the_past() -> None:
    with pytest.raises(VoteEndDateNotInFutureError):
        make_vote(end_date=_NOW - timedelta(days=1), now=_NOW)


def test_rejects_empty_option_label() -> None:
    with pytest.raises(ValueError):
        VoteOption(id=VoteOptionId.generate(), label="  ")


def test_rejects_reassigning_options_after_creation() -> None:
    vote = make_vote()

    with pytest.raises(ValidationError):
        vote.options = make_options("Maybe", "Definitely not")
