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


async def _register_and_login(
    client: httpx.AsyncClient, *, email: str, owner_id: str | None = None
) -> str:
    payload = _account_payload(email=email)
    body: dict = dict(payload)
    if owner_id is not None:
        body["owner_id"] = owner_id
    register_response = await client.post("/auth/register", json=body)
    assert register_response.status_code == 201

    login_response = await client.post("/auth/login", json=payload)
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


async def _create_owner(
    client: httpx.AsyncClient, access_token: str, *, nif: str = "12345678Z"
) -> str:
    owner_response = await client.post(
        "/owners",
        json=_owner_payload(nif=nif),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert owner_response.status_code == 201
    return owner_response.json()["id"]


@pytest.mark.asyncio
async def test_link_owner_success(client: httpx.AsyncClient) -> None:
    creator_token = await _register_and_login(client, email="creator@example.com")
    owner_id = await _create_owner(client, creator_token, nif="12345678Z")
    access_token = await _register_and_login(client, email="linker@example.com")

    response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "12345678Z"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["owner"]["id"] == owner_id
    assert body["owner"]["nif"] == "12345678Z"

    me_response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.json()["owner"]["id"] == owner_id


@pytest.mark.asyncio
async def test_link_owner_when_account_already_has_owner_returns_409(
    client: httpx.AsyncClient,
) -> None:
    creator_token = await _register_and_login(client, email="creator2@example.com")
    first_owner_id = await _create_owner(client, creator_token, nif="12345678Z")
    second_owner_id = await _create_owner(client, creator_token, nif="87654321X")
    access_token = await _register_and_login(
        client, email="already-linked@example.com", owner_id=first_owner_id
    )

    response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "87654321X"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "This account already has a linked owner"}
    # second_owner_id is unused beyond proving a valid, unclaimed NIF exists;
    # the request must be rejected before ever looking it up.
    assert second_owner_id


@pytest.mark.asyncio
async def test_link_owner_and_register_with_unclaimed_nif_return_identical_bodies(
    client: httpx.AsyncClient,
) -> None:
    # The core enumeration-protection property: whether a NIF matches no
    # Owner at all, or matches an Owner already linked to someone else, the
    # caller must not be able to tell the two apart.
    creator_token = await _register_and_login(client, email="creator3@example.com")
    owner_id = await _create_owner(client, creator_token, nif="12345678Z")
    already_linked_account_token = await _register_and_login(
        client, email="claims-owner@example.com", owner_id=owner_id
    )
    assert already_linked_account_token

    unknown_nif_account_token = await _register_and_login(
        client, email="unknown-nif@example.com"
    )
    unknown_nif_response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "99999999R"},
        headers={"Authorization": f"Bearer {unknown_nif_account_token}"},
    )

    already_claimed_account_token = await _register_and_login(
        client, email="already-claimed-nif@example.com"
    )
    already_claimed_response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "12345678Z"},
        headers={"Authorization": f"Bearer {already_claimed_account_token}"},
    )

    assert unknown_nif_response.status_code == 409
    assert already_claimed_response.status_code == 409
    assert unknown_nif_response.json() == already_claimed_response.json()
    assert unknown_nif_response.json() == {
        "detail": "This NIF could not be linked to your account"
    }


@pytest.mark.asyncio
async def test_link_owner_precedence_already_has_owner_wins_over_unknown_nif(
    client: httpx.AsyncClient,
) -> None:
    # An account that already has an owner AND supplies a garbage/nonexistent
    # NIF must surface AccountAlreadyHasOwnerError's message, not the unified
    # NIF-not-available one -- proves the check order, not just that both
    # errors exist somewhere.
    creator_token = await _register_and_login(client, email="creator4@example.com")
    owner_id = await _create_owner(client, creator_token, nif="12345678Z")
    access_token = await _register_and_login(
        client, email="already-linked2@example.com", owner_id=owner_id
    )

    response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "NOT-A-REAL-NIF"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "This account already has a linked owner"}


@pytest.mark.asyncio
async def test_link_owner_with_invalid_nif_format_returns_400(
    client: httpx.AsyncClient,
) -> None:
    access_token = await _register_and_login(client, email="invalid-nif@example.com")

    response = await client.post(
        "/auth/me/link-owner",
        json={"nif": "NOT-A-NIF"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_link_owner_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/auth/me/link-owner", json={"nif": "12345678Z"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_with_owner_id_already_linked_returns_409_with_distinct_message(
    client: httpx.AsyncClient,
) -> None:
    creator_token = await _register_and_login(client, email="creator5@example.com")
    owner_id = await _create_owner(client, creator_token, nif="12345678Z")
    await _register_and_login(
        client, email="first-claim@example.com", owner_id=owner_id
    )

    response = await client.post(
        "/auth/register",
        json={
            **_account_payload(email="second-claim@example.com"),
            "owner_id": owner_id,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    # Deliberately NOT the unified link-owner message: owner_id here is an
    # opaque UUID supplied by the client, not the sensitive NIF case, so no
    # enumeration protection is warranted for this endpoint.
    assert body["detail"] != "This NIF could not be linked to your account"
