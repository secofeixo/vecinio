from __future__ import annotations

import httpx
import pytest
import pytest_asyncio


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
        json={"email": "auth-owners@example.com", "password": "s3cret-password"},
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "auth-owners@example.com", "password": "s3cret-password"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _auth_headers(client)


@pytest.mark.asyncio
async def test_register_owner_returns_201_with_expected_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post("/owners", json=_owner_payload(), headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["nif"] == "12345678Z"
    assert body["full_name"] == "Jane Doe"
    assert body["email"] == "jane.doe@example.com"
    assert body["phone"] == "+34600111222"
    assert "id" in body


@pytest.mark.asyncio
async def test_duplicate_nif_returns_409_with_json_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/owners", json=_owner_payload(nif="12345678Z"), headers=auth_headers
    )

    response = await client.post(
        "/owners",
        json=_owner_payload(nif="12345678Z", email="other@example.com"),
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_invalid_nif_format_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/owners", json=_owner_payload(nif="NOT-A-NIF"), headers=auth_headers
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_register_owner_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/owners", json=_owner_payload())

    assert response.status_code == 401
