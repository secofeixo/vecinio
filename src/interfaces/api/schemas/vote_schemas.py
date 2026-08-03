from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateVoteRequest(BaseModel):
    title: str
    description: str
    option_labels: list[str] = Field(min_length=2)
    end_date: datetime


class CreateVoteResponse(BaseModel):
    vote_id: UUID


class CastBallotRequest(BaseModel):
    unit_id: UUID
    option_id: UUID


class CastBallotResponse(BaseModel):
    ballot_id: UUID


class OptionTallyResponse(BaseModel):
    option_id: UUID
    unit_count: int
    weighted_coefficient: Decimal


class CloseVoteResponse(BaseModel):
    tallies: list[OptionTallyResponse]
    total_units_in_community: int
    units_that_voted: int
    total_participation_coefficient: Decimal
    closed_at: datetime
