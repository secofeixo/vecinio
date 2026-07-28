from src.domain.owner.owner import Owner
from src.domain.owner.value_objects import NIF, Email, OwnerId, PhoneNumber


def test_creates_owner_with_all_fields() -> None:
    owner = Owner(
        id=OwnerId.generate(),
        nif=NIF(value="12345678Z"),
        full_name="Jane Doe",
        email=Email(value="jane.doe@example.com"),
        phone=PhoneNumber(value="+34612345678"),
    )

    assert owner.full_name == "Jane Doe"
    assert owner.nif.value == "12345678Z"
    assert owner.email.value == "jane.doe@example.com"
    assert owner.phone is not None
    assert owner.phone.value == "+34612345678"


def test_creates_owner_without_phone() -> None:
    owner = Owner(
        id=OwnerId.generate(),
        nif=NIF(value="12345678Z"),
        full_name="Jane Doe",
        email=Email(value="jane.doe@example.com"),
    )

    assert owner.phone is None


def test_owner_id_is_typed_value_object() -> None:
    owner = Owner(
        id=OwnerId.generate(),
        nif=NIF(value="12345678Z"),
        full_name="Jane Doe",
        email=Email(value="jane.doe@example.com"),
    )

    assert isinstance(owner.id, OwnerId)
