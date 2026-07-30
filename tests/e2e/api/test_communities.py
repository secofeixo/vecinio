from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio


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


async def _auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    await client.post(
        "/auth/register",
        json={"email": "auth-communities@example.com", "password": "s3cret-password"},
    )
    login_response = await client.post(
        "/auth/login",
        json={"email": "auth-communities@example.com", "password": "s3cret-password"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _auth_headers(client)


@pytest.mark.asyncio
async def test_create_community_returns_201_with_expected_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/communities", json=_community_payload(cif="H12345674"), headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Edificio Sol"
    assert body["cif"] == "H12345674"
    assert body["address"] == {
        "street": "Calle Mayor",
        "number": "1",
        "city": "Madrid",
        "postal_code": "28001",
        "province": "Madrid",
    }
    assert len(body["units"]) == 1
    assert body["units"][0]["identifier"] == "4º-2ª"
    assert body["units"][0]["participation_coefficient"] == "1"
    assert body["units"][0]["owner_ids"] == []


@pytest.mark.asyncio
async def test_duplicate_cif_returns_409_with_json_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/communities", json=_community_payload(cif="H12345674"), headers=auth_headers
    )

    response = await client.post(
        "/communities",
        json=_community_payload(name="Edificio Duplicado", cif="H12345674"),
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_duplicate_unit_identifier_in_same_request_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    payload = _community_payload(cif="H12345674")
    payload["units"] = [
        {"identifier": "4º-2ª", "participation_coefficient": "0.5"},
        {"identifier": "4º-2ª", "participation_coefficient": "0.5"},
    ]

    response = await client.post("/communities", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_invalid_cif_format_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/communities", json=_community_payload(cif="NOT-A-CIF"), headers=auth_headers
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_session_rolls_back_after_conflict_so_next_request_succeeds(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/communities", json=_community_payload(cif="H12345674"), headers=auth_headers
    )

    conflict_response = await client.post(
        "/communities",
        json=_community_payload(name="Edificio Duplicado", cif="H12345674"),
        headers=auth_headers,
    )
    assert conflict_response.status_code == 409

    retry_response = await client.post(
        "/communities",
        json=_community_payload(name="Edificio Nuevo", cif="A58818501"),
        headers=auth_headers,
    )
    assert retry_response.status_code == 201


@pytest.mark.asyncio
async def test_session_rolls_back_after_bad_request_so_next_request_succeeds(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    invalid_response = await client.post(
        "/communities", json=_community_payload(cif="NOT-A-CIF"), headers=auth_headers
    )
    assert invalid_response.status_code == 400

    retry_response = await client.post(
        "/communities", json=_community_payload(cif="A58818501"), headers=auth_headers
    )
    assert retry_response.status_code == 201


@pytest.mark.asyncio
async def test_get_community_returns_200_with_expected_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_response = await client.post(
        "/communities", json=_community_payload(cif="H12345674"), headers=auth_headers
    )
    community_id = create_response.json()["id"]

    response = await client.get(f"/communities/{community_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == community_id
    assert body["name"] == "Edificio Sol"
    assert body["cif"] == "H12345674"


@pytest.mark.asyncio
async def test_get_community_returns_404_for_nonexistent_id(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get(f"/communities/{uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_community_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/communities", json=_community_payload(cif="H12345674")
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_community_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"/communities/{uuid4()}")

    assert response.status_code == 401
