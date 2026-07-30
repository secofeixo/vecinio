from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.infrastructure.persistence.models import Base

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production")

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_alembic(command: str, target: str, url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        ["uv", "run", "alembic", command, target],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    # One container for the whole test session (integration + e2e). Lazily
    # instantiated: unit tests never request this fixture, so they never
    # pay for it.
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    url = postgres_container.get_connection_url()
    _run_alembic("upgrade", "head", url)
    return url


@pytest_asyncio.fixture(scope="session")
async def database_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


async def truncate_all_tables(engine: AsyncEngine) -> None:
    # Real, committed TRUNCATE against the shared container/engine — not a
    # savepoint rollback. Some integration/e2e tests open a second physical
    # connection to simulate a concurrent writer and expect to see data the
    # first session already committed; that only works if commits are real.
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )
