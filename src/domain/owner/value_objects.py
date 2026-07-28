from __future__ import annotations

import re
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator


class OwnerId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    @staticmethod
    def generate() -> OwnerId:
        return OwnerId(value=uuid4())


_NIF_PATTERN = re.compile(r"^[0-9]{8}[A-Z]$")
_NIE_PATTERN = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")
_CONTROL_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_SUBSTITUTES = {"X": "0", "Y": "1", "Z": "2"}


class NIF(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if _NIF_PATTERN.match(value):
            digits, control = value[:8], value[8]
        elif _NIE_PATTERN.match(value):
            digits = _NIE_PREFIX_SUBSTITUTES[value[0]] + value[1:8]
            control = value[8]
        else:
            raise ValueError(f"Invalid NIF/NIE format: {value}")

        expected_control = _CONTROL_LETTERS[int(digits) % 23]
        if control != expected_control:
            raise ValueError(f"Invalid NIF/NIE control letter: {value}")

        return value


class Email(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError(f"Invalid email format: {value}")
        return value


_PHONE_NUMBER_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


class PhoneNumber(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, value: str) -> str:
        if not _PHONE_NUMBER_PATTERN.match(value):
            raise ValueError(f"Invalid phone number format: {value}")
        return value
