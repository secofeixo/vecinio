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

# NOTE on the concurrent-modification (412) scenario: the repository-level
# test test_concurrent_save_raises_concurrent_modification_error (see
# tests/integration/infrastructure/test_community_repository.py) already
# covers this path by holding two sessions open and interleaving reads/saves.
# An equivalent HTTP-level test isn't meaningful with the current design:
# CommunityResponse never exposes `version`, and AssignOwnerToUnit.execute()
# always does its own get_by_id fresh, inside the same call that saves - so a
# client (or a sequence of ordinary HTTP calls) has no way to supply a stale
# read the way the repository-level test does by hand. Reproducing the race
# through the API would require two requests genuinely overlapping in-flight,
# forced deterministic via test-only synchronization scaffolding, which would
# be nontrivial hook wiring for coverage the repository-level test already
# provides. Skipped here by agreement; flagged rather than forced.


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


def _community_payload(name: str = "Edificio Sol", cif: str = "H12345674") -> dict:
    return {
        "name": name,
        "street": "Calle Mayor",
        "number": "1",
        "city": "Madrid",
        "postal_code": "28001",
        "province": "Madrid",
        "cif": cif,
        "units": [{"identifier": "4º-2ª", "participation_coefficient": "1"}],
    }


def _owner_payload(nif: str = "12345678Z", email: str = "jane.doe@example.com") -> dict:
    return {
        "nif": nif,
        "full_name": "Jane Doe",
        "email": email,
        "phone": "+34600111222",
    }


async def _auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    await client.post(
        "/auth/register",
        json={"email": "auth-assign@example.com", "password": "s3cret-password"},
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "auth-assign@example.com", "password": "s3cret-password"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _auth_headers(client)


async def _create_community(
    client: httpx.AsyncClient, auth_headers: dict[str, str], **kwargs: str
) -> dict:
    response = await client.post(
        "/communities", json=_community_payload(**kwargs), headers=auth_headers
    )
    assert response.status_code == 201
    return response.json()


async def _create_owner(
    client: httpx.AsyncClient, auth_headers: dict[str, str], **kwargs: str
) -> dict:
    response = await client.post(
        "/owners", json=_owner_payload(**kwargs), headers=auth_headers
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_assign_owner_to_unit_returns_200_with_updated_owner_ids(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    unit_id = community["units"][0]["id"]
    owner = await _create_owner(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": owner["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    updated_unit = next(unit for unit in body["units"] if unit["id"] == unit_id)
    assert updated_unit["owner_ids"] == [owner["id"]]


@pytest.mark.asyncio
async def test_assign_owner_to_unit_returns_404_for_nonexistent_community(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    owner = await _create_owner(client, auth_headers)

    response = await client.post(
        f"/communities/{uuid4()}/units/{uuid4()}/owners",
        json={"owner_id": owner["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_assign_owner_to_unit_returns_404_for_nonexistent_unit(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    owner = await _create_owner(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/units/{uuid4()}/owners",
        json={"owner_id": owner["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_assign_owner_to_unit_returns_404_for_nonexistent_owner(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    unit_id = community["units"][0]["id"]

    response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": str(uuid4())},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_assign_owner_to_unit_returns_409_when_already_assigned(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    unit_id = community["units"][0]["id"]
    owner = await _create_owner(client, auth_headers)

    first_response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": owner["id"]},
        headers=auth_headers,
    )
    assert first_response.status_code == 200

    second_response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": owner["id"]},
        headers=auth_headers,
    )

    assert second_response.status_code == 409
    assert "detail" in second_response.json()


@pytest.mark.asyncio
async def test_assign_owner_to_unit_without_auth_header_returns_401(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    unit_id = community["units"][0]["id"]
    owner = await _create_owner(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": owner["id"]},
    )

    assert response.status_code == 401
