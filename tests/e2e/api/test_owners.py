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


def _community_payload(
    name: str = "Edificio Sol",
    cif: str = "H12345674",
    units: list[dict] | None = None,
) -> dict:
    return {
        "name": name,
        "street": "Calle Mayor",
        "number": "1",
        "city": "Madrid",
        "postal_code": "28001",
        "province": "Madrid",
        "cif": cif,
        "units": (
            units
            if units is not None
            else [{"identifier": "4º-2ª", "participation_coefficient": "1"}]
        ),
    }


async def _register_and_login(
    client: httpx.AsyncClient, email: str, owner_id: str | None = None
) -> str:
    payload: dict = {"email": email, "password": "s3cret-password"}
    if owner_id is not None:
        payload["owner_id"] = owner_id
    await client.post("/auth/register", json=payload)
    login_response = await client.post(
        "/auth/login", json={"email": email, "password": "s3cret-password"}
    )
    return login_response.json()["access_token"]


async def _create_community(
    client: httpx.AsyncClient, headers: dict[str, str], **kwargs: object
) -> dict:
    response = await client.post(
        "/communities", json=_community_payload(**kwargs), headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def _assign_owner(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    community_id: str,
    unit_id: str,
    owner_id: str,
) -> httpx.Response:
    return await client.post(
        f"/communities/{community_id}/units/{unit_id}/owners",
        json={"owner_id": owner_id},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_get_my_units_returns_units_across_multiple_communities(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    owner_response = await client.post(
        "/owners", json=_owner_payload(), headers=auth_headers
    )
    assert owner_response.status_code == 201
    owner_id = owner_response.json()["id"]

    linked_token = await _register_and_login(
        client, email="linked-multi@example.com", owner_id=owner_id
    )

    community1 = await _create_community(client, auth_headers, cif="H12345674")
    community2 = await _create_community(
        client, auth_headers, cif="A58818501", name="Edificio Luna"
    )
    unit1_id = community1["units"][0]["id"]
    unit2_id = community2["units"][0]["id"]

    assert (
        await _assign_owner(client, auth_headers, community1["id"], unit1_id, owner_id)
    ).status_code == 200
    assert (
        await _assign_owner(client, auth_headers, community2["id"], unit2_id, owner_id)
    ).status_code == 200

    response = await client.get(
        "/owners/me/units", headers={"Authorization": f"Bearer {linked_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    by_community = {item["community_id"]: item for item in body}
    assert by_community[community1["id"]]["id"] == unit1_id
    assert by_community[community1["id"]]["community_name"] == "Edificio Sol"
    assert by_community[community2["id"]]["id"] == unit2_id
    assert by_community[community2["id"]]["community_name"] == "Edificio Luna"
    assert by_community[community2["id"]]["community_address"] == {
        "street": "Calle Mayor",
        "number": "1",
        "city": "Madrid",
        "postal_code": "28001",
        "province": "Madrid",
    }


@pytest.mark.asyncio
async def test_get_my_units_excludes_units_not_owned_by_caller(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    target_owner = (
        await client.post(
            "/owners",
            json=_owner_payload(nif="12345678Z", email="target@example.com"),
            headers=auth_headers,
        )
    ).json()
    other_owner = (
        await client.post(
            "/owners",
            json=_owner_payload(nif="87654321X", email="other@example.com"),
            headers=auth_headers,
        )
    ).json()
    linked_token = await _register_and_login(
        client, email="linked-excl@example.com", owner_id=target_owner["id"]
    )

    community = await _create_community(
        client,
        auth_headers,
        units=[
            {"identifier": "1ºA", "participation_coefficient": "0.5"},
            {"identifier": "1ºB", "participation_coefficient": "0.5"},
        ],
    )
    my_unit_id = community["units"][0]["id"]
    other_unit_id = community["units"][1]["id"]

    assert (
        await _assign_owner(
            client, auth_headers, community["id"], my_unit_id, target_owner["id"]
        )
    ).status_code == 200
    assert (
        await _assign_owner(
            client, auth_headers, community["id"], other_unit_id, other_owner["id"]
        )
    ).status_code == 200

    response = await client.get(
        "/owners/me/units", headers={"Authorization": f"Bearer {linked_token}"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [my_unit_id]


@pytest.mark.asyncio
async def test_get_my_units_returns_empty_list_when_owner_has_no_units(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    owner = (
        await client.post("/owners", json=_owner_payload(), headers=auth_headers)
    ).json()
    linked_token = await _register_and_login(
        client, email="linked-empty@example.com", owner_id=owner["id"]
    )

    response = await client.get(
        "/owners/me/units", headers={"Authorization": f"Bearer {linked_token}"}
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_my_units_without_linked_owner_returns_404(
    client: httpx.AsyncClient,
) -> None:
    token = await _register_and_login(client, email="no-owner@example.com")

    response = await client.get(
        "/owners/me/units", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No owner is linked to this account"}


@pytest.mark.asyncio
async def test_get_my_units_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/owners/me/units")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_units_with_co_owned_unit_included_once(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    target_owner = (
        await client.post(
            "/owners",
            json=_owner_payload(nif="12345678Z", email="co-target@example.com"),
            headers=auth_headers,
        )
    ).json()
    co_owner = (
        await client.post(
            "/owners",
            json=_owner_payload(nif="87654321X", email="co-other@example.com"),
            headers=auth_headers,
        )
    ).json()
    linked_token = await _register_and_login(
        client, email="linked-co@example.com", owner_id=target_owner["id"]
    )

    community = await _create_community(client, auth_headers)
    unit_id = community["units"][0]["id"]

    assert (
        await _assign_owner(
            client, auth_headers, community["id"], unit_id, target_owner["id"]
        )
    ).status_code == 200
    assert (
        await _assign_owner(
            client, auth_headers, community["id"], unit_id, co_owner["id"]
        )
    ).status_code == 200

    response = await client.get(
        "/owners/me/units", headers={"Authorization": f"Bearer {linked_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == unit_id
