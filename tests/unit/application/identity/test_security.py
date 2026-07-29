from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.application.identity.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_hash_password_does_not_return_the_plaintext() -> None:
    assert hash_password("correct-password") != "correct-password"


def test_verify_password_accepts_the_correct_password() -> None:
    hashed = hash_password("correct-password")
    assert verify_password("correct-password", hashed) is True


def test_verify_password_rejects_the_wrong_password() -> None:
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_long_password_beyond_72_bytes_is_not_truncated() -> None:
    # Explicit behavior check requested for whichever hashing scheme is
    # chosen: bcrypt silently ignores bytes past a 72-byte input (a known
    # footgun — two passwords sharing the same first 72 bytes would hash
    # identically). argon2 (via pwdlib), the backend chosen here, has no such
    # limit: it feeds the entire input into the KDF, so two long passwords
    # that only differ after byte 72 must still hash and verify differently.
    base = "a" * 100
    password_one = base + "-one"
    password_two = base + "-two"
    assert len(password_one.encode()) > 72

    hashed_one = hash_password(password_one)

    assert verify_password(password_one, hashed_one) is True
    assert verify_password(password_two, hashed_one) is False


def test_access_token_round_trips_the_subject() -> None:
    token = create_access_token("some-account-id")
    assert decode_access_token(token) == "some-account-id"


def test_expired_access_token_raises_on_decode() -> None:
    issued_at = datetime.now(timezone.utc) - timedelta(hours=1)
    token = create_access_token("some-account-id", now=issued_at)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_hash_refresh_token_is_deterministic_and_not_the_raw_value() -> None:
    hashed = hash_refresh_token("raw-refresh-token")
    assert hashed != "raw-refresh-token"
    assert hashed == hash_refresh_token("raw-refresh-token")
