from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_DOWN, Decimal

from src.domain.community.value_objects import UnitId

from .quota import QuotaAllocationSumMismatchError
from .quota_allocation import QuotaAllocation

_CENT = Decimal("0.01")


def allocate_largest_remainder(
    total: Decimal, unit_coefficients: Sequence[tuple[UnitId, Decimal]]
) -> tuple[QuotaAllocation, ...]:
    if not unit_coefficients:
        return ()

    truncated_amounts: list[Decimal] = []
    remainders: list[Decimal] = []
    for _, coefficient in unit_coefficients:
        raw = total * coefficient
        truncated = raw.quantize(_CENT, rounding=ROUND_DOWN)
        truncated_amounts.append(truncated)
        remainders.append(raw - truncated)

    distributed = sum(truncated_amounts, Decimal("0"))
    leftover_cents = int(((total - distributed) / _CENT).to_integral_value())

    # Stable sort keeps the original (Community.units) order as the
    # tie-break for units with an identical discarded remainder.
    ranked_indices = sorted(
        range(len(unit_coefficients)),
        key=lambda index: remainders[index],
        reverse=True,
    )
    indices_to_bump = set(ranked_indices[:leftover_cents])

    final_amounts = [
        amount + _CENT if index in indices_to_bump else amount
        for index, amount in enumerate(truncated_amounts)
    ]

    allocated_total = sum(final_amounts, Decimal("0"))
    if allocated_total != total:
        raise QuotaAllocationSumMismatchError(
            f"Largest remainder allocation produced {allocated_total}, "
            f"expected {total}"
        )

    return tuple(
        QuotaAllocation(
            unit_id=unit_id,
            participation_coefficient=coefficient,
            amount=amount,
        )
        for (unit_id, coefficient), amount in zip(
            unit_coefficients, final_amounts, strict=True
        )
    )
