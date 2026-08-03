from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

_PASSWORD = "s3cret-password"  # pragma: allowlist secret


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


def _vote_payload(
    title: str = "Aprobar presupuesto 2027",
    description: str = "Votación del presupuesto ordinario",
    option_labels: list[str] | None = None,
    end_date: str | None = None,
) -> dict:
    return {
        "title": title,
        "description": description,
        "option_labels": option_labels or ["A favor", "En contra"],
        "end_date": end_date or _future_end_date(),
    }


def _future_end_date() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


def _past_end_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


async def _register_and_login(
    client: httpx.AsyncClient, email: str, owner_id: str | None = None
) -> dict[str, str]:
    payload: dict = {"email": email, "password": _PASSWORD}
    if owner_id is not None:
        payload["owner_id"] = owner_id
    await client.post("/auth/register", json=payload)
    login_response = await client.post(
        "/auth/login", json={"email": email, "password": _PASSWORD}
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _register_and_login(client, "auth-votes@example.com")


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


async def _create_community_with_voter(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> tuple[dict, dict[str, str]]:
    """Creates a community with one unit, an owner assigned to that unit, and
    a login account linked to that owner -- the account authorized to create
    votes for the community.
    """
    community = await _create_community(client, admin_headers)
    unit_id = community["units"][0]["id"]
    owner = await _create_owner(client, admin_headers)

    assign_response = await client.post(
        f"/communities/{community['id']}/units/{unit_id}/owners",
        json={"owner_id": owner["id"]},
        headers=admin_headers,
    )
    assert assign_response.status_code == 200

    voter_headers = await _register_and_login(
        client, f"voter-{owner['id']}@example.com", owner_id=owner["id"]
    )
    return community, voter_headers


@pytest.mark.asyncio
async def test_create_vote_returns_201_with_vote_id(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(),
        headers=voter_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert "vote_id" in body
    UUID(body["vote_id"])  # Round-trips as a UUID.


@pytest.mark.asyncio
async def test_create_vote_without_auth_header_returns_401(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes", json=_vote_payload()
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_vote_for_nonexistent_community_returns_404_with_fixed_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"/communities/{uuid4()}/votes",
        json=_vote_payload(),
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Community not found or you are not a member of it"
    }


@pytest.mark.asyncio
async def test_create_vote_by_account_without_unit_returns_404_with_same_fixed_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers)
    # auth_headers' account has no owner_id link at all, so it owns no unit
    # anywhere -- AccountNotAuthorizedToCreateVoteError, not
    # CommunityNotFoundError, but the response must be byte-identical to the
    # nonexistent-community case above so callers can't tell the two apart.
    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(),
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Community not found or you are not a member of it"
    }

    nonexistent_response = await client.post(
        f"/communities/{uuid4()}/votes",
        json=_vote_payload(),
        headers=auth_headers,
    )
    assert response.content == nonexistent_response.content


@pytest.mark.asyncio
async def test_create_vote_by_owner_of_different_community_returns_404_with_same_fixed_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # voter_headers' account owns a unit in community X, but the request
    # targets community Y, where it owns nothing -- still
    # AccountNotAuthorizedToCreateVoteError, must stay byte-identical to the
    # nonexistent-community and no-unit-anywhere cases.
    _community_x, voter_headers = await _create_community_with_voter(
        client, auth_headers
    )
    community_y = await _create_community(client, auth_headers, cif="A58818501")

    response = await client.post(
        f"/communities/{community_y['id']}/votes",
        json=_vote_payload(),
        headers=voter_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Community not found or you are not a member of it"
    }

    nonexistent_response = await client.post(
        f"/communities/{uuid4()}/votes",
        json=_vote_payload(),
        headers=voter_headers,
    )
    assert response.content == nonexistent_response.content


@pytest.mark.asyncio
async def test_create_vote_for_nonexistent_community_with_invalid_payload_returns_404_not_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Precedence check: the community-existence check runs before the Vote
    # aggregate is ever constructed, so an invalid payload (end_date in the
    # past) against a nonexistent community must still surface as 404, not
    # 400 -- the community check wins.
    response = await client.post(
        f"/communities/{uuid4()}/votes",
        json=_vote_payload(end_date=_past_end_date()),
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Community not found or you are not a member of it"
    }


@pytest.mark.asyncio
async def test_create_vote_by_non_member_with_invalid_payload_returns_404_not_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Precedence check, membership side: the community exists, but
    # auth_headers' account owns no unit in it -- that authorization check
    # must win over Vote construction, so an otherwise-invalid payload
    # (end_date in the past) still surfaces as 404, not 400.
    community = await _create_community(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(end_date=_past_end_date()),
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Community not found or you are not a member of it"
    }


@pytest.mark.asyncio
async def test_create_vote_with_past_end_date_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(end_date=_past_end_date()),
        headers=voter_headers,
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_vote_with_duplicate_option_labels_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(option_labels=["A favor", "A favor"]),
        headers=voter_headers,
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_vote_with_single_option_returns_422(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Rejected by Pydantic's Field(min_length=2) at the schema boundary --
    # InsufficientVoteOptionsError in the domain is unreachable via HTTP,
    # defense in depth only, already covered by the domain's own unit test.
    community, voter_headers = await _create_community_with_voter(client, auth_headers)

    response = await client.post(
        f"/communities/{community['id']}/votes",
        json=_vote_payload(option_labels=["Solo una opción"]),
        headers=voter_headers,
    )

    assert response.status_code == 422
