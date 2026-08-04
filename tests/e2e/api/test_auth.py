from __future__ import annotations

from uuid import uuid4

import httpx
import pytest


def _account_payload(
    email: str = "jane.doe@example.com", password: str = "s3cret-password"
) -> dict:
    return {"email": email, "password": password}


def _owner_payload(nif: str = "12345678Z", email: str = "owner@example.com") -> dict:
    return {
        "nif": nif,
        "full_name": "Jane Doe",
        "email": email,
        "phone": "+34600111222",
    }


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
            "units": [{"identifier": "4º-2ª", "participation_coefficient": "1"}],
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


@pytest.mark.asyncio
async def test_get_me_without_linked_owner_returns_200_with_null_owner(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/auth/register", json=_account_payload())
    login_response = await client.post("/auth/login", json=_account_payload())
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "id" in body
    assert body["email"] == _account_payload()["email"]
    assert body["owner"] is None


@pytest.mark.asyncio
async def test_get_me_with_linked_owner_returns_200_with_embedded_owner(
    client: httpx.AsyncClient,
) -> None:
    creator_payload = _account_payload(email="owner-creator@example.com")
    await client.post("/auth/register", json=creator_payload)
    creator_login = await client.post("/auth/login", json=creator_payload)
    creator_token = creator_login.json()["access_token"]

    owner_response = await client.post(
        "/owners",
        json=_owner_payload(),
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert owner_response.status_code == 201
    owner_id = owner_response.json()["id"]

    linked_payload = _account_payload(email="linked-account@example.com")
    register_response = await client.post(
        "/auth/register", json={**linked_payload, "owner_id": owner_id}
    )
    assert register_response.status_code == 201
    login_response = await client.post("/auth/login", json=linked_payload)
    access_token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["owner"] == {
        "id": owner_id,
        "nif": "12345678Z",
        "full_name": "Jane Doe",
        "email": "owner@example.com",
        "phone": "+34600111222",
    }


@pytest.mark.asyncio
async def test_get_me_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_malformed_token_returns_401_with_expected_body(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/auth/register", json=_account_payload())
    login_response = await client.post("/auth/login", json=_account_payload())
    access_token = login_response.json()["access_token"]
    header_and_payload, _, _ = access_token.rpartition(".")
    tampered_token = f"{header_and_payload}.tampered-signature"

    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
