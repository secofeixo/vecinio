from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _database_url() -> str:
    try:
        return os.environ["DATABASE_URL"]
    except KeyError as error:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Expected a postgresql+psycopg:// connection string."
        ) from error


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(_database_url())


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
