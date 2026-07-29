from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.security import decode_access_token
from src.domain.identity.account import Account
from src.domain.identity.value_objects import AccountId
from src.infrastructure.persistence.account_repository import PostgresAccountRepository
from src.infrastructure.persistence.database import get_session_factory

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def get_current_account(
    token: str = Depends(oauth2_scheme),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Account:
    invalid_token_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        subject = decode_access_token(token)
        account_id = AccountId(value=UUID(subject))
    except (jwt.InvalidTokenError, ValueError) as error:
        raise invalid_token_error from error

    repository = PostgresAccountRepository(session)
    account = await repository.get_by_id(account_id)
    if account is None:
        raise invalid_token_error

    return account
