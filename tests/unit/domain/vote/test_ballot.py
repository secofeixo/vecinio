from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.domain.community.value_objects import UnitId
from src.domain.owner.value_objects import OwnerId
from src.domain.vote.ballot import (
    Ballot,
    BallotAlreadySupersededError,
    BallotCannotSupersedeItselfError,
)
from src.domain.vote.value_objects import BallotId, VoteId, VoteOptionId

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_ballot(now: datetime = _NOW) -> Ballot:
    return Ballot.create(
        id=BallotId.generate(),
        vote_id=VoteId.generate(),
        unit_id=UnitId.generate(),
        option_id=VoteOptionId.generate(),
        cast_by_owner_id=OwnerId.generate(),
        now=now,
    )


def test_creates_ballot_with_valid_data() -> None:
    ballot_id = BallotId.generate()
    vote_id = VoteId.generate()
    unit_id = UnitId.generate()
    option_id = VoteOptionId.generate()
    owner_id = OwnerId.generate()

    ballot = Ballot.create(
        id=ballot_id,
        vote_id=vote_id,
        unit_id=unit_id,
        option_id=option_id,
        cast_by_owner_id=owner_id,
        now=_NOW,
    )

    assert ballot.id == ballot_id
    assert ballot.vote_id == vote_id
    assert ballot.unit_id == unit_id
    assert ballot.option_id == option_id
    assert ballot.cast_by_owner_id == owner_id
    assert ballot.cast_at == _NOW
    assert ballot.superseded_by_ballot_id is None


def test_rejects_reassigning_vote_id_after_creation() -> None:
    ballot = make_ballot()

    with pytest.raises(ValidationError):
        ballot.vote_id = VoteId.generate()


def test_rejects_reassigning_unit_id_after_creation() -> None:
    ballot = make_ballot()

    with pytest.raises(ValidationError):
        ballot.unit_id = UnitId.generate()


def test_rejects_reassigning_option_id_after_creation() -> None:
    ballot = make_ballot()

    with pytest.raises(ValidationError):
        ballot.option_id = VoteOptionId.generate()


def test_rejects_reassigning_cast_by_owner_id_after_creation() -> None:
    ballot = make_ballot()

    with pytest.raises(ValidationError):
        ballot.cast_by_owner_id = OwnerId.generate()


def test_rejects_reassigning_cast_at_after_creation() -> None:
    ballot = make_ballot()

    with pytest.raises(ValidationError):
        ballot.cast_at = datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_supersede_marks_ballot_as_superseded() -> None:
    ballot = make_ballot()
    superseding_ballot_id = BallotId.generate()

    ballot.supersede(superseding_ballot_id)

    assert ballot.superseded_by_ballot_id == superseding_ballot_id


def test_supersede_twice_raises_already_superseded_error() -> None:
    ballot = make_ballot()
    ballot.supersede(BallotId.generate())

    with pytest.raises(BallotAlreadySupersededError):
        ballot.supersede(BallotId.generate())


def test_supersede_with_own_id_raises_cannot_supersede_itself_error() -> None:
    ballot = make_ballot()

    with pytest.raises(BallotCannotSupersedeItselfError):
        ballot.supersede(ballot.id)


def test_supersede_with_own_id_takes_precedence_over_already_superseded() -> None:
    ballot = make_ballot()
    ballot.supersede(BallotId.generate())

    with pytest.raises(BallotCannotSupersedeItselfError):
        ballot.supersede(ballot.id)
