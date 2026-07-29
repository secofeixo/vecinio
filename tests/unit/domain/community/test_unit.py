from decimal import Decimal

import pytest

from src.domain.community.unit import Unit
from src.domain.community.value_objects import ParticipationCoefficient, UnitId


def make_coefficient() -> ParticipationCoefficient:
    return ParticipationCoefficient(value=Decimal("1"))


def test_accepts_non_empty_identifier() -> None:
    unit = Unit(
        id=UnitId.generate(),
        identifier="4º-2ª",
        participation_coefficient=make_coefficient(),
    )

    assert unit.identifier == "4º-2ª"


def test_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError):
        Unit(
            id=UnitId.generate(),
            identifier="",
            participation_coefficient=make_coefficient(),
        )


def test_rejects_whitespace_only_identifier() -> None:
    with pytest.raises(ValueError):
        Unit(
            id=UnitId.generate(),
            identifier="   ",
            participation_coefficient=make_coefficient(),
        )
