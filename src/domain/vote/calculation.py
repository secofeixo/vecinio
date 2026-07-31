from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from src.domain.community.unit import Unit
from src.domain.community.value_objects import UnitId

from .ballot import Ballot
from .value_objects import VoteOptionId
from .vote import VoteDomainError
from .vote_option import VoteOption
from .vote_result import OptionTally, VoteResult


class InconsistentBallotStateError(VoteDomainError):
    pass


class BallotReferencesUnknownUnitError(VoteDomainError):
    pass


def calculate_vote_result(
    *,
    ballots: Sequence[Ballot],
    units: Sequence[Unit],
    options: Sequence[VoteOption],
    now: datetime,
) -> VoteResult:
    active_ballots = [
        ballot for ballot in ballots if ballot.superseded_by_ballot_id is None
    ]

    active_ballots_by_unit: dict[UnitId, list[Ballot]] = defaultdict(list)
    for ballot in active_ballots:
        active_ballots_by_unit[ballot.unit_id].append(ballot)

    for unit_id, unit_ballots in active_ballots_by_unit.items():
        if len(unit_ballots) > 1:
            raise InconsistentBallotStateError(
                f"Unit {unit_id} has {len(unit_ballots)} active ballots, "
                "expected at most 1"
            )

    units_by_id = {unit.id: unit for unit in units}

    unit_counts: dict[VoteOptionId, int] = defaultdict(int)
    weighted_coefficients: dict[VoteOptionId, Decimal] = defaultdict(
        lambda: Decimal("0")
    )
    for ballot in active_ballots:
        unit = units_by_id.get(ballot.unit_id)
        if unit is None:
            raise BallotReferencesUnknownUnitError(
                f"Ballot {ballot.id} references unit {ballot.unit_id}, "
                "which is not present in the given units"
            )
        unit_counts[ballot.option_id] += 1
        weighted_coefficients[ballot.option_id] += unit.participation_coefficient.value

    tallies = tuple(
        OptionTally(
            option_id=option.id,
            unit_count=unit_counts[option.id],
            weighted_coefficient=weighted_coefficients[option.id],
        )
        for option in options
    )

    total_participation_coefficient = sum(
        (tally.weighted_coefficient for tally in tallies), Decimal("0")
    )

    return VoteResult(
        tallies=tallies,
        total_units_in_community=len(units),
        units_that_voted=len(active_ballots_by_unit),
        total_participation_coefficient=total_participation_coefficient,
        closed_at=now,
    )
