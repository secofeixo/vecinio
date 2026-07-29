from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import uuid4

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


def _account_payload(
    email: str = "jane.doe@example.com", password: str = "s3cret-password"
) -> dict:
    return {"email": email, "password": password}


@pytest.mark.asyncio
async def test_register_returns_201_without_leaking_hash_or_tokens(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/register", json=_account_payload())

    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert "password_hash" not in body
    assert "access_token" not in body
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_duplicate_email_registration_returns_409(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/auth/register", json=_account_payload())

    response = await client.post("/auth/register", json=_account_payload())

    assert response.status_code == 409
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_register_with_nonexistent_owner_id_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/auth/register",
        json={**_account_payload(), "owner_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client: httpx.AsyncClient) -> None:
    await client.post("/auth/register", json=_account_payload())

    response = await client.post(
        "/auth/login",
        json=_account_payload(password="wrong-password"),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_unregistered_email_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/login", json=_account_payload())

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_full_auth_flow_register_login_access_refresh_logout(
    client: httpx.AsyncClient,
) -> None:
    register_response = await client.post("/auth/register", json=_account_payload())
    assert register_response.status_code == 201

    # Registration does not auto-login: a protected endpoint must reject a
    # request made before /auth/login has ever been called.
    unauthenticated_response = await client.get(f"/communities/{uuid4()}")
    assert unauthenticated_response.status_code == 401

    login_response = await client.post("/auth/login", json=_account_payload())
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    create_response = await client.post(
        "/communities",
        json={
            "name": "Edificio Sol",
            "street": "Calle Mayor",
            "number": "1",
            "city": "Madrid",
            "postal_code": "28001",
            "province": "Madrid",
            "cif": "H12345674",
            "units": [{"participation_coefficient": "1"}],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 201

    community_id = create_response.json()["id"]
    no_token_response = await client.get(f"/communities/{community_id}")
    assert no_token_response.status_code == 401

    authenticated_response = await client.get(
        f"/communities/{community_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert authenticated_response.status_code == 200

    refresh_response = await client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["access_token"]
    assert new_access_token

    reused_new_token_response = await client.get(
        f"/communities/{community_id}",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert reused_new_token_response.status_code == 200

    logout_response = await client.post(
        "/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout_response.status_code == 204

    refresh_after_logout_response = await client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refresh_after_logout_response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_unknown_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/auth/refresh", json={"refresh_token": "never-issued"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_unknown_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/logout", json={"refresh_token": "never-issued"})

    assert response.status_code == 401
