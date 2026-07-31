from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.domain.community.unit import Unit
from src.domain.community.value_objects import ParticipationCoefficient, UnitId
from src.domain.owner.value_objects import OwnerId
from src.domain.vote.ballot import Ballot
from src.domain.vote.calculation import (
    BallotReferencesUnknownUnitError,
    InconsistentBallotStateError,
    calculate_vote_result,
)
from src.domain.vote.value_objects import BallotId, VoteId, VoteOptionId
from src.domain.vote.vote_option import VoteOption

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_unit(coefficient: str) -> Unit:
    return Unit(
        id=UnitId.generate(),
        identifier=f"unit-{coefficient}",
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
    )


def make_option(label: str = "Option") -> VoteOption:
    return VoteOption(id=VoteOptionId.generate(), label=label)


def make_ballot(
    unit_id: UnitId,
    option_id: VoteOptionId,
    superseded_by_ballot_id: BallotId | None = None,
) -> Ballot:
    ballot = Ballot.create(
        id=BallotId.generate(),
        vote_id=VoteId.generate(),
        unit_id=unit_id,
        option_id=option_id,
        cast_by_owner_id=OwnerId.generate(),
        now=_NOW,
    )
    if superseded_by_ballot_id is not None:
        ballot.supersede(superseded_by_ballot_id)
    return ballot


def test_tallies_ballots_split_across_options() -> None:
    unit_a = make_unit("0.3")
    unit_b = make_unit("0.2")
    unit_c = make_unit("0.5")
    option_yes = make_option("Yes")
    option_no = make_option("No")

    ballots = [
        make_ballot(unit_a.id, option_yes.id),
        make_ballot(unit_b.id, option_yes.id),
        make_ballot(unit_c.id, option_no.id),
    ]

    result = calculate_vote_result(
        ballots=ballots,
        units=[unit_a, unit_b, unit_c],
        options=[option_yes, option_no],
        now=_NOW,
    )

    tallies_by_option = {tally.option_id: tally for tally in result.tallies}
    assert tallies_by_option[option_yes.id].unit_count == 2
    assert tallies_by_option[option_yes.id].weighted_coefficient == Decimal("0.5")
    assert tallies_by_option[option_no.id].unit_count == 1
    assert tallies_by_option[option_no.id].weighted_coefficient == Decimal("0.5")


def test_units_without_any_ballot_count_in_total_but_not_in_units_that_voted() -> None:
    voting_unit = make_unit("0.4")
    non_voting_unit = make_unit("0.6")
    option = make_option()

    ballots = [make_ballot(voting_unit.id, option.id)]

    result = calculate_vote_result(
        ballots=ballots,
        units=[voting_unit, non_voting_unit],
        options=[option],
        now=_NOW,
    )

    assert result.total_units_in_community == 2
    assert result.units_that_voted == 1
    assert len(result.tallies) == 1
    assert result.tallies[0].unit_count == 1


def test_superseded_ballot_does_not_count_only_active_ballot_does() -> None:
    superseded_unit = make_unit("0.3")
    active_unit = make_unit("0.7")
    superseded_option = make_option("Superseded")
    active_option = make_option("Active")

    superseded_ballot = make_ballot(
        superseded_unit.id,
        superseded_option.id,
        superseded_by_ballot_id=BallotId.generate(),
    )
    active_ballot = make_ballot(active_unit.id, active_option.id)

    result = calculate_vote_result(
        ballots=[superseded_ballot, active_ballot],
        units=[superseded_unit, active_unit],
        options=[superseded_option, active_option],
        now=_NOW,
    )

    assert result.units_that_voted == 1
    tallies_by_option = {tally.option_id: tally for tally in result.tallies}
    assert tallies_by_option[active_option.id].unit_count == 1
    assert tallies_by_option[superseded_option.id].unit_count == 0
    assert tallies_by_option[superseded_option.id].weighted_coefficient == Decimal("0")


def test_two_active_ballots_for_same_unit_raises_inconsistent_state_error() -> None:
    unit = make_unit("1")
    option_a = make_option("A")
    option_b = make_option("B")

    ballot_1 = Ballot.create(
        id=BallotId.generate(),
        vote_id=VoteId.generate(),
        unit_id=unit.id,
        option_id=option_a.id,
        cast_by_owner_id=OwnerId.generate(),
        now=_NOW,
    )
    ballot_2 = Ballot.create(
        id=BallotId.generate(),
        vote_id=VoteId.generate(),
        unit_id=unit.id,
        option_id=option_b.id,
        cast_by_owner_id=OwnerId.generate(),
        now=_NOW,
    )

    with pytest.raises(InconsistentBallotStateError):
        calculate_vote_result(
            ballots=[ballot_1, ballot_2],
            units=[unit],
            options=[option_a, option_b],
            now=_NOW,
        )


def test_total_participation_coefficient_matches_sum_of_tallies() -> None:
    unit_a = make_unit("0.25")
    unit_b = make_unit("0.35")
    unit_c = make_unit("0.4")
    option_a = make_option("A")
    option_b = make_option("B")

    ballots = [
        make_ballot(unit_a.id, option_a.id),
        make_ballot(unit_b.id, option_a.id),
        make_ballot(unit_c.id, option_b.id),
    ]

    result = calculate_vote_result(
        ballots=ballots,
        units=[unit_a, unit_b, unit_c],
        options=[option_a, option_b],
        now=_NOW,
    )

    assert result.total_participation_coefficient == sum(
        (tally.weighted_coefficient for tally in result.tallies), Decimal("0")
    )


def test_closed_at_is_set_to_now() -> None:
    unit = make_unit("1")
    option = make_option()
    ballots = [make_ballot(unit.id, option.id)]

    result = calculate_vote_result(
        ballots=ballots, units=[unit], options=[option], now=_NOW
    )

    assert result.closed_at == _NOW


def test_option_with_no_votes_still_appears_in_tallies() -> None:
    unit_a = make_unit("0.5")
    unit_b = make_unit("0.5")
    option_voted_a = make_option("A")
    option_voted_b = make_option("B")
    option_unvoted = make_option("C")

    ballots = [
        make_ballot(unit_a.id, option_voted_a.id),
        make_ballot(unit_b.id, option_voted_b.id),
    ]

    result = calculate_vote_result(
        ballots=ballots,
        units=[unit_a, unit_b],
        options=[option_voted_a, option_voted_b, option_unvoted],
        now=_NOW,
    )

    assert len(result.tallies) == 3
    tallies_by_option = {tally.option_id: tally for tally in result.tallies}
    assert tallies_by_option[option_unvoted.id].unit_count == 0
    assert tallies_by_option[option_unvoted.id].weighted_coefficient == Decimal("0")


def test_ballot_referencing_unknown_unit_raises_domain_error() -> None:
    known_unit = make_unit("1")
    option = make_option()
    ballot_for_unknown_unit = make_ballot(UnitId.generate(), option.id)

    with pytest.raises(BallotReferencesUnknownUnitError):
        calculate_vote_result(
            ballots=[ballot_for_unknown_unit],
            units=[known_unit],
            options=[option],
            now=_NOW,
        )
