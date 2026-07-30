from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.infrastructure.persistence.community_group_repository import (
    PostgresCommunityGroupRepository,
)


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
        json={
            "email": "auth-community-groups@example.com",
            "password": "s3cret-password",  # pragma: allowlist secret
        },
    )
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "auth-community-groups@example.com",
            "password": "s3cret-password",  # pragma: allowlist secret
        },
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return await _auth_headers(client)


async def _create_community(
    client: httpx.AsyncClient, auth_headers: dict[str, str], cif: str
) -> str:
    response = await client.post(
        "/communities", json=_community_payload(cif=cif), headers=auth_headers
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_community_group_returns_201_with_expected_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_a = await _create_community(client, auth_headers, cif="H12345674")
    community_b = await _create_community(client, auth_headers, cif="A58818501")

    response = await client.post(
        "/community-groups",
        json={"name": "206-208", "community_ids": [community_a, community_b]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "206-208"
    assert body["slug"] == "206-208"
    assert set(body["member_community_ids"]) == {community_a, community_b}


@pytest.mark.asyncio
async def test_duplicate_slug_returns_400(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_a = await _create_community(client, auth_headers, cif="H12345674")
    community_b = await _create_community(client, auth_headers, cif="A58818501")
    community_c = await _create_community(client, auth_headers, cif="B65451338")
    community_d = await _create_community(client, auth_headers, cif="F35155696")

    await client.post(
        "/community-groups",
        json={"name": "Jardín", "community_ids": [community_a, community_b]},
        headers=auth_headers,
    )

    response = await client.post(
        "/community-groups",
        json={"name": "jardin", "community_ids": [community_c, community_d]},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_add_community_to_group_returns_200_with_updated_members(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_a = await _create_community(client, auth_headers, cif="H12345674")
    community_b = await _create_community(client, auth_headers, cif="A58818501")
    community_c = await _create_community(client, auth_headers, cif="B65451338")

    create_response = await client.post(
        "/community-groups",
        json={"name": "206-208", "community_ids": [community_a, community_b]},
        headers=auth_headers,
    )
    group_id = create_response.json()["id"]

    response = await client.post(
        f"/community-groups/{group_id}/communities/{community_c}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["member_community_ids"]) == {community_a, community_b, community_c}


@pytest.mark.asyncio
async def test_remove_community_from_group_returns_200_with_updated_members(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community_a = await _create_community(client, auth_headers, cif="H12345674")
    community_b = await _create_community(client, auth_headers, cif="A58818501")
    community_c = await _create_community(client, auth_headers, cif="B65451338")

    create_response = await client.post(
        "/community-groups",
        json={
            "name": "206-208",
            "community_ids": [community_a, community_b, community_c],
        },
        headers=auth_headers,
    )
    group_id = create_response.json()["id"]

    response = await client.delete(
        f"/community-groups/{group_id}/communities/{community_c}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["member_community_ids"]) == {community_a, community_b}


@pytest.mark.asyncio
async def test_add_community_to_nonexistent_group_returns_404(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community = await _create_community(client, auth_headers, cif="H12345674")

    response = await client.post(
        f"/community-groups/{uuid4()}/communities/{community}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_remove_community_from_nonexistent_group_returns_404(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.delete(
        f"/community-groups/{uuid4()}/communities/{uuid4()}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_concurrent_mutations_through_http_return_412_for_the_losing_request(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A plain asyncio.gather of the two HTTP calls isn't enough to force a real
    # race: both requests reliably ran to completion sequentially (200, 200),
    # never racing, because there's no guarantee the two DB round trips
    # actually interleave. To get the same deterministic setup the
    # repository-level test achieves by manually sequencing two independent
    # sessions (test_community_group_repository.py::
    # test_concurrent_save_raises_concurrent_modification_error), a barrier is
    # used to force both requests' reads of the group to complete before
    # either is allowed to proceed to mutate + save -- everything else
    # (routing, the use case, the real repository, the real Postgres
    # container, exception_handlers.py) runs unmodified, so this still proves
    # ConcurrentModificationError is actually wired to a 412 response on these
    # routes, not just raised at the repository level.
    community_a = await _create_community(client, auth_headers, cif="H12345674")
    community_b = await _create_community(client, auth_headers, cif="A58818501")
    community_c = await _create_community(client, auth_headers, cif="B65451338")
    community_d = await _create_community(client, auth_headers, cif="F35155696")

    create_response = await client.post(
        "/community-groups",
        json={
            "name": "206-208",
            "community_ids": [community_a, community_b, community_c],
        },
        headers=auth_headers,
    )
    group_id = create_response.json()["id"]

    # Only patched now: create_community_group's own post-creation get_by_id
    # (above) must not hit the barrier, or it would hang waiting for a second
    # party that never arrives.
    barrier_timeout_seconds = 5.0
    barrier = asyncio.Barrier(2)
    original_get_by_id = PostgresCommunityGroupRepository.get_by_id

    async def get_by_id_after_barrier(
        self: PostgresCommunityGroupRepository, group_id: object
    ) -> object:
        result = await original_get_by_id(self, group_id)  # type: ignore[arg-type]
        try:
            await asyncio.wait_for(barrier.wait(), timeout=barrier_timeout_seconds)
        except (TimeoutError, asyncio.BrokenBarrierError) as error:
            # If the other concurrent request fails before its own get_by_id
            # call (e.g. auth, routing, or request parsing broke), it never
            # reaches the barrier -- without this, this branch would hang
            # forever instead of failing, and this test would become the one
            # that silently hangs the whole pipeline instead of reporting the
            # actual regression.
            raise AssertionError(
                "The other concurrent request never reached the barrier "
                f"within {barrier_timeout_seconds}s -- it likely failed "
                "before its own get_by_id call instead of racing normally."
            ) from error
        return result

    monkeypatch.setattr(
        PostgresCommunityGroupRepository, "get_by_id", get_by_id_after_barrier
    )

    add_response, remove_response = await asyncio.gather(
        client.post(
            f"/community-groups/{group_id}/communities/{community_d}",
            headers=auth_headers,
        ),
        client.delete(
            f"/community-groups/{group_id}/communities/{community_c}",
            headers=auth_headers,
        ),
    )

    statuses = {add_response.status_code, remove_response.status_code}
    assert statuses == {200, 412}

    loser = remove_response if add_response.status_code == 200 else add_response
    assert "detail" in loser.json()


@pytest.mark.asyncio
async def test_create_community_group_without_auth_header_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/community-groups", json={"name": "206-208", "community_ids": []}
    )

    assert response.status_code == 401
