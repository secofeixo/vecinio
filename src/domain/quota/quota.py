from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from src.domain.community.value_objects import CommunityId

from .quota_allocation import QuotaAllocation
from .quota_line import QuotaLine
from .value_objects import QuotaId, QuotaType


class QuotaDomainError(Exception):
    pass


class EmptyQuotaLinesError(QuotaDomainError):
    pass


class InvalidQuotaTotalError(QuotaDomainError):
    pass


class InvalidQuotaPeriodError(QuotaDomainError):
    pass


class EmptyQuotaAllocationsError(QuotaDomainError):
    pass


class DuplicateAllocationUnitError(QuotaDomainError):
    pass


class QuotaAllocationSumMismatchError(QuotaDomainError):
    pass


class ConcurrentModificationError(QuotaDomainError):
    pass


class Quota(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: QuotaId
    community_id: CommunityId
    type: QuotaType
    period_start: date
    period_end: date
    lines: tuple[QuotaLine, ...]
    allocations: tuple[QuotaAllocation, ...]
    supersedes_quota_id: QuotaId | None = None
    version: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0"))

    @model_validator(mode="after")
    def _check_invariants(self) -> Quota:
        self._check_lines_are_valid(self.lines)
        self._check_period_is_valid(self.period_start, self.period_end)
        self._check_total_is_valid(self.total)
        self._check_allocations_are_valid(self.allocations, self.total)
        return self

    @staticmethod
    def _check_lines_are_valid(lines: tuple[QuotaLine, ...]) -> None:
        if not lines:
            raise EmptyQuotaLinesError("A quota must have at least one line")

    @staticmethod
    def _check_period_is_valid(period_start: date, period_end: date) -> None:
        if period_start > period_end:
            raise InvalidQuotaPeriodError(
                f"period_start {period_start} must not be after period_end "
                f"{period_end}"
            )

    @staticmethod
    def _check_total_is_valid(total: Decimal) -> None:
        if total <= Decimal("0"):
            raise InvalidQuotaTotalError(
                f"Quota total must be strictly positive, got {total}"
            )

    @staticmethod
    def _check_allocations_are_valid(
        allocations: tuple[QuotaAllocation, ...], total: Decimal
    ) -> None:
        if not allocations:
            raise EmptyQuotaAllocationsError(
                "A quota must have at least one allocation"
            )

        unit_ids = [allocation.unit_id for allocation in allocations]
        if len(unit_ids) != len(set(unit_ids)):
            raise DuplicateAllocationUnitError(
                "Allocation unit ids must be unique within a quota"
            )

        allocated_total = sum(
            (allocation.amount for allocation in allocations), Decimal("0")
        )
        if allocated_total != total:
            raise QuotaAllocationSumMismatchError(
                f"Sum of allocation amounts ({allocated_total}) does not match "
                f"quota total ({total})"
            )
