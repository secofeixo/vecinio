import pytest

from src.domain.identity.account import Account, AccountAlreadyHasOwnerError
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.value_objects import OwnerId


def test_creates_account_with_owner_link() -> None:
    owner_id = OwnerId.generate()
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",
        owner_id=owner_id,
    )

    assert account.email.value == "jane.doe@example.com"
    assert account.password_hash == "hashed-value"
    assert account.owner_id == owner_id
    assert account.version == 0


def test_creates_account_without_owner_link() -> None:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",
    )

    assert account.owner_id is None


def test_account_id_is_typed_value_object() -> None:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",
    )

    assert isinstance(account.id, AccountId)


def test_link_owner_sets_owner_id() -> None:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",
    )
    owner_id = OwnerId.generate()

    account.link_owner(owner_id)

    assert account.owner_id == owner_id


def test_link_owner_raises_when_account_already_has_an_owner() -> None:
    account = Account(
        id=AccountId.generate(),
        email=Email(value="jane.doe@example.com"),
        password_hash="hashed-value",
        owner_id=OwnerId.generate(),
    )

    with pytest.raises(AccountAlreadyHasOwnerError):
        account.link_owner(OwnerId.generate())
