from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.conftest import truncate_all_tables


@pytest_asyncio.fixture
async def session(database_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await truncate_all_tables(database_engine)
