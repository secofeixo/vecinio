from decimal import Decimal

import pytest

from src.domain.community.value_objects import CIF, ParticipationCoefficient

# CIF: format is 1 organization letter + 7 digits + 1 control character.
# Control character rules:
#   - digit required for: A, B, E, H
#   - letter required for: K, P, Q, S
#   - either accepted for: C, D, F, G, J, L, M, N, R, U, V, W


def test_accepts_valid_cif_with_numeric_control_digit() -> None:
    assert CIF(value="H12345674").value == "H12345674"


def test_accepts_valid_cif_with_letter_control_character() -> None:
    assert CIF(value="P1234567D").value == "P1234567D"


def test_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        CIF(value="H1234567")

    with pytest.raises(ValueError):
        CIF(value="H123456744")


def test_rejects_invalid_organization_letter() -> None:
    with pytest.raises(ValueError):
        CIF(value="I12345674")


def test_rejects_non_digit_characters_in_middle_block() -> None:
    with pytest.raises(ValueError):
        CIF(value="H123A5674")


def test_rejects_incorrect_control_checksum() -> None:
    with pytest.raises(ValueError):
        CIF(value="H12345675")


def test_rejects_digit_control_where_letter_required() -> None:
    with pytest.raises(ValueError):
        CIF(value="P12345674")


def test_rejects_letter_control_where_digit_required() -> None:
    with pytest.raises(ValueError):
        CIF(value="H1234567D")


def test_accepts_valid_cif_for_f_with_digit_control() -> None:
    assert CIF(value="F12345674").value == "F12345674"


def test_accepts_valid_cif_for_g_with_digit_control() -> None:
    assert CIF(value="G12345674").value == "G12345674"


def test_accepts_valid_cif_for_f_with_letter_control() -> None:
    assert CIF(value="F1234567D").value == "F1234567D"


def test_accepts_valid_cif_for_g_with_letter_control() -> None:
    assert CIF(value="G1234567D").value == "G1234567D"


def test_participation_coefficient_accepts_value_within_range() -> None:
    assert ParticipationCoefficient(value=Decimal("0.5")).value == Decimal("0.5")


def test_participation_coefficient_accepts_upper_boundary_one() -> None:
    assert ParticipationCoefficient(value=Decimal("1")).value == Decimal("1")


def test_participation_coefficient_rejects_zero() -> None:
    with pytest.raises(ValueError):
        ParticipationCoefficient(value=Decimal("0"))


def test_participation_coefficient_rejects_negative() -> None:
    with pytest.raises(ValueError):
        ParticipationCoefficient(value=Decimal("-0.1"))


def test_participation_coefficient_rejects_value_above_one() -> None:
    with pytest.raises(ValueError):
        ParticipationCoefficient(value=Decimal("1.01"))
