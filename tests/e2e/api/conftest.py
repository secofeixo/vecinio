from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.interfaces.api.dependencies import get_session
from src.interfaces.api.main import app
from tests.conftest import truncate_all_tables


def _make_get_session_override(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncIterator[AsyncSession]]:
    # Mirrors src/interfaces/api/dependencies.py's get_session exactly, but bound
    # to a session factory pointing at the testcontainer instead of DATABASE_URL,
    # so the same commit-on-success / rollback-on-exception behavior under test
    # is what actually runs the requests below.
    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    return _get_session


@pytest_asyncio.fixture
async def client(database_engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    app.dependency_overrides[get_session] = _make_get_session_override(session_factory)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await truncate_all_tables(database_engine)
