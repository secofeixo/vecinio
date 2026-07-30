from datetime import date
from decimal import Decimal

import pytest

from src.domain.community.value_objects import CommunityId, UnitId
from src.domain.quota.quota import (
    DuplicateAllocationUnitError,
    EmptyQuotaAllocationsError,
    EmptyQuotaLinesError,
    InvalidQuotaPeriodError,
    InvalidQuotaTotalError,
    Quota,
    QuotaAllocationSumMismatchError,
)
from src.domain.quota.quota_allocation import QuotaAllocation
from src.domain.quota.quota_line import QuotaLine
from src.domain.quota.value_objects import QuotaId, QuotaType


def make_quota(
    lines: tuple[QuotaLine, ...] | None = None,
    allocations: tuple[QuotaAllocation, ...] | None = None,
    type: QuotaType = QuotaType.ORDINARY,
    period_start: date = date(2026, 1, 1),  # noqa: B008
    period_end: date = date(2026, 12, 31),  # noqa: B008
) -> Quota:
    lines = (
        lines
        if lines is not None
        else (QuotaLine(concept="Ascensor", amount=Decimal("100.00")),)
    )
    allocations = (
        allocations
        if allocations is not None
        else (
            QuotaAllocation(
                unit_id=UnitId.generate(),
                participation_coefficient=Decimal("1"),
                amount=Decimal("100.00"),
            ),
        )
    )
    return Quota(
        id=QuotaId.generate(),
        community_id=CommunityId.generate(),
        type=type,
        period_start=period_start,
        period_end=period_end,
        lines=lines,
        allocations=allocations,
    )


def test_total_is_computed_from_lines_not_accepted_as_input() -> None:
    lines = (
        QuotaLine(concept="Ascensor", amount=Decimal("70.00")),
        QuotaLine(concept="Jardín", amount=Decimal("30.00")),
    )
    allocations = (
        QuotaAllocation(
            unit_id=UnitId.generate(),
            participation_coefficient=Decimal("1"),
            amount=Decimal("100.00"),
        ),
    )

    quota = make_quota(lines=lines, allocations=allocations)

    assert quota.total == Decimal("100.00")


def test_rejects_empty_lines() -> None:
    with pytest.raises(EmptyQuotaLinesError):
        make_quota(lines=())


def test_rejects_non_positive_total() -> None:
    lines = (
        QuotaLine(concept="Cuota", amount=Decimal("50.00")),
        QuotaLine(concept="Subvención", amount=Decimal("-50.00")),
    )
    allocations = (
        QuotaAllocation(
            unit_id=UnitId.generate(),
            participation_coefficient=Decimal("1"),
            amount=Decimal("0.00"),
        ),
    )

    with pytest.raises(InvalidQuotaTotalError):
        make_quota(lines=lines, allocations=allocations)


def test_rejects_inverted_period() -> None:
    with pytest.raises(InvalidQuotaPeriodError):
        make_quota(period_start=date(2026, 12, 31), period_end=date(2026, 1, 1))


def test_rejects_empty_allocations() -> None:
    with pytest.raises(EmptyQuotaAllocationsError):
        make_quota(allocations=())


def test_rejects_duplicate_allocation_unit() -> None:
    shared_unit_id = UnitId.generate()
    allocations = (
        QuotaAllocation(
            unit_id=shared_unit_id,
            participation_coefficient=Decimal("0.5"),
            amount=Decimal("50.00"),
        ),
        QuotaAllocation(
            unit_id=shared_unit_id,
            participation_coefficient=Decimal("0.5"),
            amount=Decimal("50.00"),
        ),
    )

    with pytest.raises(DuplicateAllocationUnitError):
        make_quota(allocations=allocations)


def test_rejects_allocation_sum_mismatched_with_total() -> None:
    allocations = (
        QuotaAllocation(
            unit_id=UnitId.generate(),
            participation_coefficient=Decimal("1"),
            amount=Decimal("99.00"),
        ),
    )

    with pytest.raises(QuotaAllocationSumMismatchError):
        make_quota(allocations=allocations)


def test_accepts_ordinary_type() -> None:
    quota = make_quota(type=QuotaType.ORDINARY)
    assert quota.type is QuotaType.ORDINARY


def test_accepts_extraordinary_type() -> None:
    quota = make_quota(type=QuotaType.EXTRAORDINARY)
    assert quota.type is QuotaType.EXTRAORDINARY
