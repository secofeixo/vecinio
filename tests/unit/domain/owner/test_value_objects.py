import pytest

from src.domain.owner.value_objects import NIF, Email, PhoneNumber

# NIF: national ID is 8 digits + control letter.
# NIE (foreign resident) is X/Y/Z + 7 digits + control letter, where X/Y/Z
# substitute for 0/1/2 respectively before computing the checksum.
# Control letter = number mod 23, indexed into "TRWAGMYFPDXBNJZSQVHLCKE".


def test_accepts_valid_nif() -> None:
    assert NIF(value="12345678Z").value == "12345678Z"


def test_rejects_nif_with_wrong_control_letter() -> None:
    with pytest.raises(ValueError):
        NIF(value="12345678A")


def test_rejects_nif_with_wrong_length() -> None:
    with pytest.raises(ValueError):
        NIF(value="1234567Z")

    with pytest.raises(ValueError):
        NIF(value="123456789Z")


def test_rejects_nif_with_non_digit_in_number_block() -> None:
    with pytest.raises(ValueError):
        NIF(value="1234567AZ")


def test_accepts_valid_nie_x_prefix() -> None:
    assert NIF(value="X1234567L").value == "X1234567L"


def test_accepts_valid_nie_y_prefix() -> None:
    assert NIF(value="Y1234567X").value == "Y1234567X"


def test_accepts_valid_nie_z_prefix() -> None:
    assert NIF(value="Z1234567R").value == "Z1234567R"


def test_rejects_nie_with_wrong_control_letter() -> None:
    with pytest.raises(ValueError):
        NIF(value="X1234567A")


def test_rejects_nie_with_invalid_prefix_letter() -> None:
    with pytest.raises(ValueError):
        NIF(value="A1234567L")


def test_rejects_nie_with_wrong_length() -> None:
    with pytest.raises(ValueError):
        NIF(value="X123456L")

    with pytest.raises(ValueError):
        NIF(value="X12345678L")


def test_rejects_empty_nif() -> None:
    with pytest.raises(ValueError):
        NIF(value="")


def test_rejects_lowercase_nif() -> None:
    with pytest.raises(ValueError):
        NIF(value="12345678z")


def test_rejects_lowercase_nie() -> None:
    with pytest.raises(ValueError):
        NIF(value="x1234567l")


def test_accepts_valid_email() -> None:
    assert Email(value="owner@example.com").value == "owner@example.com"


def test_rejects_email_without_at_symbol() -> None:
    with pytest.raises(ValueError):
        Email(value="owner.example.com")


def test_rejects_email_without_domain() -> None:
    with pytest.raises(ValueError):
        Email(value="owner@")


def test_rejects_empty_email() -> None:
    with pytest.raises(ValueError):
        Email(value="")


def test_accepts_valid_phone_number_without_country_code() -> None:
    assert PhoneNumber(value="612345678").value == "612345678"


def test_accepts_valid_phone_number_with_plus_prefix() -> None:
    assert PhoneNumber(value="+34612345678").value == "+34612345678"


def test_accepts_valid_uk_phone_number() -> None:
    assert PhoneNumber(value="+447911123456").value == "+447911123456"


def test_accepts_valid_german_phone_number() -> None:
    assert PhoneNumber(value="+4915123456789").value == "+4915123456789"


def test_accepts_phone_number_at_minimum_length_boundary() -> None:
    assert PhoneNumber(value="1234567").value == "1234567"


def test_accepts_phone_number_at_maximum_length_boundary() -> None:
    assert PhoneNumber(value="123456789012345").value == "123456789012345"


def test_rejects_phone_number_too_short() -> None:
    with pytest.raises(ValueError):
        PhoneNumber(value="123456")


def test_rejects_phone_number_too_long() -> None:
    with pytest.raises(ValueError):
        PhoneNumber(value="+1234567890123456")


def test_rejects_phone_number_with_non_digit_characters() -> None:
    with pytest.raises(ValueError):
        PhoneNumber(value="612-345-678")


def test_rejects_empty_phone_number() -> None:
    with pytest.raises(ValueError):
        PhoneNumber(value="")
