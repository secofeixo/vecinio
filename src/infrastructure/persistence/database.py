from __future__ import annotations

import os

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


engine: AsyncEngine = create_async_engine(_database_url())

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)
