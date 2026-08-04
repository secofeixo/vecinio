from __future__ import annotations

from enum import Enum

from src.domain.shared.value_objects import AggregateId


class QuotaId(AggregateId):
    pass


class QuotaType(str, Enum):
    ORDINARY = "ordinary"
    EXTRAORDINARY = "extraordinary"
