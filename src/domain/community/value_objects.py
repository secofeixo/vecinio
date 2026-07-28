from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator


class CommunityId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> CommunityId:
        return CommunityId(value=uuid4())


class UnitId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> UnitId:
        return UnitId(value=uuid4())


class Address(BaseModel):
    model_config = ConfigDict(frozen=True)

    street: str
    number: str
    city: str
    postal_code: str
    province: str


_CIF_PATTERN = re.compile(r"^[A-Z][0-9]{7}[0-9A-J]$")
_CONTROL_LETTERS = "JABCDEFGHI"
_DIGIT_CONTROL_ORGANIZATIONS = frozenset("ABEH")
_LETTER_CONTROL_ORGANIZATIONS = frozenset("KPQS")
_VALID_ORGANIZATION_LETTERS = frozenset("ABCDEFGHJKLMNPQRSUVW")


class CIF(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if not _CIF_PATTERN.match(value):
            raise ValueError(f"Invalid CIF format: {value}")

        organization_letter = value[0]
        if organization_letter not in _VALID_ORGANIZATION_LETTERS:
            raise ValueError(f"Invalid CIF organization letter: {value}")

        digits, control = value[1:8], value[8]
        expected_digit, expected_letter = cls._expected_control_characters(digits)

        if organization_letter in _DIGIT_CONTROL_ORGANIZATIONS:
            valid = control == expected_digit
        elif organization_letter in _LETTER_CONTROL_ORGANIZATIONS:
            valid = control == expected_letter
        else:
            valid = control in (expected_digit, expected_letter)

        if not valid:
            raise ValueError(f"Invalid CIF control character: {value}")

        return value

    @staticmethod
    def _expected_control_characters(digits: str) -> tuple[str, str]:
        even_sum = sum(int(digit) for digit in digits[1::2])
        odd_sum = 0
        for digit in digits[0::2]:
            doubled = int(digit) * 2
            odd_sum += doubled // 10 + doubled % 10
        control_digit = (10 - (even_sum + odd_sum) % 10) % 10
        return str(control_digit), _CONTROL_LETTERS[control_digit]


class ParticipationCoefficient(BaseModel):
    model_config = ConfigDict(frozen=True)

    FULL: ClassVar[Decimal] = Decimal("1")

    value: Decimal

    @field_validator("value")
    @classmethod
    def _within_range(cls, value: Decimal) -> Decimal:
        if not (Decimal("0") < value <= cls.FULL):
            raise ValueError(
                f"Participation coefficient must be between 0 and 1, got {value}"
            )
        return value

    @staticmethod
    def total(coefficients: Iterable[ParticipationCoefficient]) -> Decimal:
        return sum((coefficient.value for coefficient in coefficients), Decimal("0"))
