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
        "units": [
            {"identifier": "4º-2ª", "participation_coefficient": "0.6"},
            {"identifier": "Bajo A", "participation_coefficient": "0.4"},
        ],
    }


async def _auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    await client.post(
        "/auth/register",
        json={
            "email": "auth-quotas@example.com",
            "password": "s3cret-password",  # pragma: allowlist secret
        },
    )
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "auth-quotas@example.com",
            "password": "s3cret-password",  # pragma: allowlist secret
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _auth_headers(client)


async def _create_community(
    client: httpx.AsyncClient, auth_headers: dict[str, str], cif: str = "H12345674"
) -> str:
    response = await client.post(
        "/communities", json=_community_payload(cif=cif), headers=auth_headers
    )
    return response.json()["id"]


def _quota_payload(
    quota_type: str = "ordinary",
    period_start: str = "2026-01-01",
    period_end: str = "2026-12-31",
    amount: str = "100.00",
) -> dict:
    return {
        "type": quota_type,
        "period_start": period_start,
        "period_end": period_end,
        "lines": [{"concept": "Ascensor", "amount": amount}],
    }


@pytest.mark.asyncio
async def test_create_quota_returns_201_with_expected_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)

    response = await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(),
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["community_id"] == community_id
    assert body["type"] == "ordinary"
    assert body["total"] == "100.00"
    assert len(body["allocations"]) == 2
    assert sum(float(a["amount"]) for a in body["allocations"]) == 100.00
    assert {a["amount"] for a in body["allocations"]} == {"60.00", "40.00"}


@pytest.mark.asyncio
async def test_create_quota_for_nonexistent_community_returns_404(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"/communities/{uuid4()}/quotas",
        json=_quota_payload(),
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_quota_with_malformed_type_returns_422(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)

    response = await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(quota_type="not-a-type"),
        headers=auth_headers,
    )

    # Rejected by Pydantic/FastAPI enum validation at the schema boundary,
    # before any application code runs -- not a domain/application error, so
    # 422 rather than 400.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_overlapping_ordinary_quota_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)
    await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(period_start="2026-01-01", period_end="2026-06-30"),
        headers=auth_headers,
    )

    response = await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(period_start="2026-03-01", period_end="2026-09-30"),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_ordinary_quota_sharing_exact_boundary_day_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)
    await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(period_start="2026-01-01", period_end="2026-12-31"),
        headers=auth_headers,
    )

    # Existing quota ends 2026-12-31; new one starts on the exact same day --
    # inclusive on both bounds, so this must be rejected as overlapping.
    response = await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(period_start="2026-12-31", period_end="2027-06-30"),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_get_quota_returns_200_with_full_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)
    create_response = await client.post(
        f"/communities/{community_id}/quotas",
        json=_quota_payload(),
        headers=auth_headers,
    )
    quota_id = create_response.json()["id"]

    response = await client.get(
        f"/communities/{community_id}/quotas/{quota_id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == create_response.json()


@pytest.mark.asyncio
async def test_get_quota_returns_404_for_nonexistent_id(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_id = await _create_community(client, auth_headers)

    response = await client.get(
        f"/communities/{community_id}/quotas/{uuid4()}", headers=auth_headers
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_quota_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        f"/communities/{uuid4()}/quotas", json=_quota_payload()
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_quota_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/communities/{uuid4()}/quotas/{uuid4()}")

    assert response.status_code == 401
