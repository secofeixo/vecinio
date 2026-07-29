from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
JWT_ALGORITHM = "HS256"

# argon2id (via pwdlib) has no equivalent of bcrypt's 72-byte silent
# truncation: the whole password feeds the KDF regardless of length.
_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    return str(_password_hash.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(_password_hash.verify(password, password_hash))


def _jwt_secret_key() -> str:
    try:
        return os.environ["JWT_SECRET_KEY"]
    except KeyError as error:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Expected a secret key for signing JWTs."
        ) from error


def create_access_token(subject: str, *, now: datetime | None = None) -> str:
    issued_at = now if now is not None else datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": issued_at,
        "exp": issued_at + ACCESS_TOKEN_TTL,
    }
    return str(jwt.encode(payload, _jwt_secret_key(), algorithm=JWT_ALGORITHM))


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, _jwt_secret_key(), algorithms=[JWT_ALGORITHM])
    return str(payload["sub"])


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # Refresh tokens are high-entropy random values (256 bits), not
    # low-entropy human passwords, so a fast cryptographic hash is the
    # appropriate tool here — unlike password_hash, this is not brute-force
    # exposed and does not need a slow, memory-hard KDF.
    return hashlib.sha256(token.encode()).hexdigest()
