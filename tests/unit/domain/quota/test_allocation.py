from collections.abc import Sequence
from decimal import ROUND_DOWN, Decimal

import pytest

from src.domain.community.value_objects import UnitId
from src.domain.quota.allocation import allocate_largest_remainder
from src.domain.quota.quota_allocation import QuotaAllocation

_CENT = Decimal("0.01")


def _assert_largest_remainder_property(
    total: Decimal,
    unit_coefficients: Sequence[tuple[UnitId, Decimal]],
    allocations: tuple[QuotaAllocation, ...],
) -> None:
    assert sum((allocation.amount for allocation in allocations), Decimal("0")) == total

    remainders = []
    bumped = []
    for (unit_id, coefficient), allocation in zip(
        unit_coefficients, allocations, strict=True
    ):
        assert allocation.unit_id == unit_id
        raw = total * coefficient
        truncated = raw.quantize(_CENT, rounding=ROUND_DOWN)
        remainders.append(raw - truncated)
        if allocation.amount == truncated:
            bumped.append(False)
        elif allocation.amount == truncated + _CENT:
            bumped.append(True)
        else:
            pytest.fail(
                f"Allocation amount {allocation.amount} is neither the truncated "
                f"value {truncated} nor truncated+0.01"
            )

    # The defining property of the largest-remainder method: no unbumped unit
    # may have a strictly larger discarded remainder than a bumped one.
    for i, remainder_i in enumerate(remainders):
        for j, remainder_j in enumerate(remainders):
            if not bumped[i] and bumped[j] and remainder_i > remainder_j:
                pytest.fail(
                    f"Unit {i} (remainder {remainder_i}) was skipped while unit "
                    f"{j} (remainder {remainder_j}) was bumped"
                )


def test_even_split_needs_no_remainder_distribution() -> None:
    total = Decimal("100.00")
    unit_coefficients = [(UnitId.generate(), Decimal("0.25")) for _ in range(4)]

    allocations = allocate_largest_remainder(total, unit_coefficients)

    assert all(allocation.amount == Decimal("25.00") for allocation in allocations)
    _assert_largest_remainder_property(total, unit_coefficients, allocations)


def test_three_units_uneven_split_bumps_largest_remainder() -> None:
    total = Decimal("100.00")
    unit_coefficients = [
        (UnitId.generate(), Decimal("0.333333333333")),
        (UnitId.generate(), Decimal("0.333333333333")),
        (UnitId.generate(), Decimal("0.333333333334")),
    ]

    allocations = allocate_largest_remainder(total, unit_coefficients)

    # Hand-verified: raw amounts are 33.3333333333, 33.3333333333,
    # 33.3333333334 — all truncate to 33.33, leaving a single leftover cent
    # that must go to the third unit (the largest discarded remainder).
    assert [allocation.amount for allocation in allocations] == [
        Decimal("33.33"),
        Decimal("33.33"),
        Decimal("33.34"),
    ]
    _assert_largest_remainder_property(total, unit_coefficients, allocations)


def test_seven_units_that_do_not_divide_evenly() -> None:
    total = Decimal("100.00")
    unit_coefficients = [(UnitId.generate(), Decimal("0.142857")) for _ in range(6)]
    unit_coefficients.append((UnitId.generate(), Decimal("0.142858")))

    allocations = allocate_largest_remainder(total, unit_coefficients)

    _assert_largest_remainder_property(total, unit_coefficients, allocations)


def test_eleven_units_that_do_not_divide_evenly() -> None:
    total = Decimal("1000.00")
    base = Decimal("0.0909090909")
    unit_coefficients = [(UnitId.generate(), base) for _ in range(10)]
    remaining = Decimal("1") - base * 10
    unit_coefficients.append((UnitId.generate(), remaining))

    allocations = allocate_largest_remainder(total, unit_coefficients)

    _assert_largest_remainder_property(total, unit_coefficients, allocations)


def test_many_decimal_coefficients_still_sum_exactly() -> None:
    total = Decimal("12345.67")
    unit_coefficients = [
        (UnitId.generate(), Decimal("0.123456789012")),
        (UnitId.generate(), Decimal("0.234567890123")),
        (UnitId.generate(), Decimal("0.641975320865")),
    ]
    assert sum(coefficient for _, coefficient in unit_coefficients) == Decimal("1")

    allocations = allocate_largest_remainder(total, unit_coefficients)

    _assert_largest_remainder_property(total, unit_coefficients, allocations)


def test_deterministic_tie_break_uses_original_order() -> None:
    total = Decimal("100.01")
    unit_a = UnitId.generate()
    unit_b = UnitId.generate()
    unit_coefficients = [(unit_a, Decimal("0.5")), (unit_b, Decimal("0.5"))]

    allocations = allocate_largest_remainder(total, unit_coefficients)

    # Both units discard an identical 0.005 remainder; only one leftover cent
    # exists, so the tie must resolve deterministically to the first unit in
    # the input order.
    assert allocations[0].unit_id == unit_a
    assert allocations[0].amount == Decimal("50.01")
    assert allocations[1].unit_id == unit_b
    assert allocations[1].amount == Decimal("50.00")


def test_single_unit_gets_the_entire_total() -> None:
    total = Decimal("10.00")
    unit_id = UnitId.generate()

    allocations = allocate_largest_remainder(total, [(unit_id, Decimal("1"))])

    assert allocations == (
        QuotaAllocation(
            unit_id=unit_id, participation_coefficient=Decimal("1"), amount=total
        ),
    )
