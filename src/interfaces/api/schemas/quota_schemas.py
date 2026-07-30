from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from src.domain.quota.value_objects import QuotaType


class QuotaLineRequest(BaseModel):
    concept: str
    amount: Decimal


class CreateQuotaRequest(BaseModel):
    type: QuotaType
    period_start: date
    period_end: date
    lines: list[QuotaLineRequest]


class QuotaLineResponse(BaseModel):
    concept: str
    amount: Decimal


class QuotaAllocationResponse(BaseModel):
    unit_id: UUID
    participation_coefficient: Decimal
    amount: Decimal


class QuotaResponse(BaseModel):
    id: UUID
    community_id: UUID
    type: QuotaType
    period_start: date
    period_end: date
    lines: list[QuotaLineResponse]
    total: Decimal
    allocations: list[QuotaAllocationResponse]
    supersedes_quota_id: UUID | None
    version: int
