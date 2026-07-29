import pytest

from src.domain.identity.value_objects import AccountId, Email, RefreshTokenId


def test_accepts_valid_email() -> None:
    assert Email(value="account@example.com").value == "account@example.com"


def test_rejects_email_without_at_symbol() -> None:
    with pytest.raises(ValueError):
        Email(value="account.example.com")


def test_rejects_email_without_domain() -> None:
    with pytest.raises(ValueError):
        Email(value="account@")


def test_rejects_empty_email() -> None:
    with pytest.raises(ValueError):
        Email(value="")


def test_account_id_generate_produces_unique_values() -> None:
    assert AccountId.generate() != AccountId.generate()


def test_refresh_token_id_generate_produces_unique_values() -> None:
    assert RefreshTokenId.generate() != RefreshTokenId.generate()
