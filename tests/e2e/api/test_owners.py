from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.interfaces.api.dependencies import get_session
from src.interfaces.api.main import app

REPO_ROOT = Path(__file__).resolve().parents[3]


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


@pytest.fixture(scope="module")
def postgres_container() -> AsyncIterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        yield container


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
async def client(
    postgres_container: PostgresContainer,
) -> AsyncIterator[httpx.AsyncClient]:
    url = postgres_container.get_connection_url()
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app.dependency_overrides[get_session] = _make_get_session_override(session_factory)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()
    _run_alembic("downgrade", "base", url)


def _owner_payload(nif: str = "12345678Z", email: str = "jane.doe@example.com") -> dict:
    return {
        "nif": nif,
        "full_name": "Jane Doe",
        "email": email,
        "phone": "+34600111222",
    }


@pytest.mark.asyncio
async def test_register_owner_returns_201_with_expected_body(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/owners", json=_owner_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["nif"] == "12345678Z"
    assert body["full_name"] == "Jane Doe"
    assert body["email"] == "jane.doe@example.com"
    assert body["phone"] == "+34600111222"
    assert "id" in body


@pytest.mark.asyncio
async def test_duplicate_nif_returns_409_with_json_body(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/owners", json=_owner_payload(nif="12345678Z"))

    response = await client.post(
        "/owners",
        json=_owner_payload(nif="12345678Z", email="other@example.com"),
    )

    assert response.status_code == 409
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_invalid_nif_format_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.post("/owners", json=_owner_payload(nif="NOT-A-NIF"))

    assert response.status_code == 400
    assert "detail" in response.json()
