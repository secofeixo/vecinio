from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from src.domain.community.value_objects import CommunityId
from src.domain.identity.value_objects import AccountId
from src.domain.vote.value_objects import VoteId, VoteOptionId
from src.domain.vote.vote import Vote
from src.domain.vote.vote_option import VoteOption
from src.infrastructure.persistence.vote_repository import PostgresVoteRepository
from src.interfaces.api.main import app as fastapi_app

_PASSWORD = "s3cret-password"  # pragma: allowlist secret

# NOTE on the CommunityNotFoundError (500) scenario in CastBallot: a
# persisted Vote pointing at a Community that no longer exists. There is no
# mechanism to delete a Community anywhere in this codebase today (verified
# via `grep -rn "delete_community|DeleteCommunity|remove_community" src/` --
# the only hit, remove_community_from_group, unlinks a Community from a
# CommunityGroup, it does not delete the Community aggregate). This is NOT a
# deliberate design invariant ("communities are never deleted") -- it is
# simply a use case that has not been built yet, and could exist in the
# future. Reaching this state via HTTP today would require deliberately
# bypassing the domain (inserting a Vote whose community_id was never a real
# Community, via direct repository access) purely to force a state the
# system never produces through any real code path. Decided explicitly: not
# worth a test whose own setup defeats the invariant it would be proving.
# Do not add this test back without discussing it first.


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
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    *,
    cif: str = "H12345674",
    nif: str = "12345678Z",
) -> tuple[dict, dict[str, str]]:
    """Creates a community with one unit, an owner assigned to that unit, and
    a login account linked to that owner -- the account authorized to create
    votes for the community.
    """
    community = await _create_community(client, admin_headers, cif=cif)
    unit_id = community["units"][0]["id"]
    owner = await _create_owner(client, admin_headers, nif=nif)

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


async def _create_community_with_two_owners_on_unit(
    client: httpx.AsyncClient, admin_headers: dict[str, str]
) -> tuple[dict, dict[str, str], dict[str, str]]:
    """Community with a single unit and TWO distinct owners assigned to it.

    Confirmed against src/domain/community/community.py's
    Community.assign_owner_to_unit (`owner_ids=target.owner_ids +
    (owner_id,)`) that a second POST .../owners call with a different
    owner_id ADDS to the unit's existing owner_ids rather than replacing it
    -- this is what makes genuine co-ownership reachable through two
    ordinary API calls, not a bypass.
    """
    community = await _create_community(client, admin_headers)
    unit_id = community["units"][0]["id"]

    owner_a = await _create_owner(
        client, admin_headers, nif="12345678Z", email="owner-a@example.com"
    )
    owner_b = await _create_owner(
        client, admin_headers, nif="X1234567L", email="owner-b@example.com"
    )

    for owner in (owner_a, owner_b):
        assign_response = await client.post(
            f"/communities/{community['id']}/units/{unit_id}/owners",
            json={"owner_id": owner["id"]},
            headers=admin_headers,
        )
        assert assign_response.status_code == 200

    headers_a = await _register_and_login(
        client, f"voter-a-{owner_a['id']}@example.com", owner_id=owner_a["id"]
    )
    headers_b = await _register_and_login(
        client, f"voter-b-{owner_b['id']}@example.com", owner_id=owner_b["id"]
    )
    return community, headers_a, headers_b


async def _register_account_id(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post(
        "/auth/register", json={"email": email, "password": _PASSWORD}
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_vote(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    community_id: str,
    **kwargs: object,
) -> dict:
    response = await client.post(
        f"/communities/{community_id}/votes",
        json=_vote_payload(**kwargs),  # type: ignore[arg-type]
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def _cast_ballot(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    vote_id: str,
    unit_id: str,
    option_id: str,
) -> httpx.Response:
    return await client.post(
        f"/votes/{vote_id}/ballots",
        json={"unit_id": unit_id, "option_id": option_id},
        headers=headers,
    )


async def _get_vote_option_ids(
    database_engine: AsyncEngine, vote_id: str
) -> tuple[UUID, ...]:
    # No GET /votes/{id} endpoint exists yet (vote's interfaces/api layer
    # only has creation-side routes so far -- see CLAUDE.md), so option ids
    # -- generated server-side and never returned by CreateVoteResponse --
    # can only be recovered by reading the persisted Vote directly.
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with session_factory() as session:
        vote = await PostgresVoteRepository(session).get_by_id(
            VoteId(value=UUID(vote_id))
        )
    assert vote is not None
    return tuple(option.id.value for option in vote.options)


async def _insert_ended_vote(
    database_engine: AsyncEngine,
    *,
    community_id: str,
    created_by_account_id: str,
) -> tuple[UUID, tuple[UUID, ...]]:
    """Persists a Vote whose end_date is already in the past.

    Uses Vote.create()'s injected `now` clock parameter with a past value --
    the sanctioned use of that parameter (end_date is only checked against
    `now` at creation time, precisely so a persisted past-dated Vote
    rehydrated later doesn't re-fail the check, per CLAUDE.md), not a domain
    bypass: the resulting row is exactly what a real Vote created before its
    own end_date would look like.
    """
    end_date = datetime.now(timezone.utc) - timedelta(days=1)
    creation_now = end_date - timedelta(hours=1)
    options = (
        VoteOption(id=VoteOptionId.generate(), label="A favor"),
        VoteOption(id=VoteOptionId.generate(), label="En contra"),
    )
    vote = Vote.create(
        id=VoteId.generate(),
        community_id=CommunityId(value=UUID(community_id)),
        title="Vote inserted directly, already ended",
        description="Setup for VoteHasEndedError e2e tests",
        options=options,
        end_date=end_date,
        created_by_account_id=AccountId(value=UUID(created_by_account_id)),
        now=creation_now,
    )

    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with session_factory() as session:
        await PostgresVoteRepository(session).save(vote)
        await session.commit()

    return vote.id.value, tuple(option.id.value for option in vote.options)


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


@pytest.mark.asyncio
async def test_cast_ballot_returns_201_with_ballot_id(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], unit_id, str(option_ids[0])
    )

    assert response.status_code == 201
    body = response.json()
    assert "ballot_id" in body
    UUID(body["ballot_id"])  # Round-trips as a UUID.


@pytest.mark.asyncio
async def test_cast_ballot_correction_by_same_owner_returns_201_with_new_ballot_id(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    first_response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], unit_id, str(option_ids[0])
    )
    assert first_response.status_code == 201

    second_response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], unit_id, str(option_ids[1])
    )

    assert second_response.status_code == 201
    assert second_response.json()["ballot_id"] != first_response.json()["ballot_id"]


@pytest.mark.asyncio
async def test_cast_ballot_for_nonexistent_vote_returns_404_with_fixed_body(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await _cast_ballot(
        client, auth_headers, str(uuid4()), str(uuid4()), str(uuid4())
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Vote not found"}


@pytest.mark.asyncio
async def test_cast_ballot_after_vote_end_date_returns_409(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    unit_id = community["units"][0]["id"]
    creator_account_id = await _register_account_id(
        client, f"vote-creator-{uuid4()}@example.com"
    )
    vote_id, option_ids = await _insert_ended_vote(
        database_engine,
        community_id=community["id"],
        created_by_account_id=creator_account_id,
    )

    response = await _cast_ballot(
        client, voter_headers, str(vote_id), unit_id, str(option_ids[0])
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cast_ballot_by_account_without_linked_owner_returns_404_with_unified_body(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    # auth_headers' account has no owner_id link at all, so it owns no unit
    # anywhere -- AccountNotAuthorizedToCastBallotError, unified deliberately
    # with the "owner doesn't own this unit" case below.
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    response = await _cast_ballot(
        client, auth_headers, vote["vote_id"], unit_id, str(option_ids[0])
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Not authorized to cast a ballot for this unit"
    }


@pytest.mark.asyncio
async def test_cast_ballot_by_owner_of_different_community_returns_404_with_same_unified_body(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    # voter_x_headers' account owns a unit in community X, but the ballot
    # targets community Y's vote and unit, where it owns nothing -- still
    # AccountNotAuthorizedToCastBallotError, must stay byte-identical to the
    # no-linked-owner case above.
    _community_x, voter_x_headers = await _create_community_with_voter(
        client, auth_headers
    )
    community_y, voter_y_headers = await _create_community_with_voter(
        client, auth_headers, cif="A58818501", nif="X1234567L"
    )
    vote = await _create_vote(client, voter_y_headers, community_y["id"])
    unit_id_y = community_y["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    response = await _cast_ballot(
        client, voter_x_headers, vote["vote_id"], unit_id_y, str(option_ids[0])
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Not authorized to cast a ballot for this unit"
    }


@pytest.mark.asyncio
async def test_cast_ballot_with_unknown_option_returns_404_with_distinct_message(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    unit_id = community["units"][0]["id"]

    response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], unit_id, str(uuid4())
    )

    assert response.status_code == 404
    assert response.json()["detail"] != "Not authorized to cast a ballot for this unit"


@pytest.mark.asyncio
async def test_cast_ballot_with_unknown_unit_returns_404_with_distinct_message(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], str(uuid4()), str(option_ids[0])
    )

    assert response.status_code == 404
    assert response.json()["detail"] != "Not authorized to cast a ballot for this unit"


@pytest.mark.asyncio
async def test_cast_ballot_for_unit_already_voted_by_different_owner_returns_409(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    community, headers_a, headers_b = await _create_community_with_two_owners_on_unit(
        client, auth_headers
    )
    vote = await _create_vote(client, headers_a, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    first_response = await _cast_ballot(
        client, headers_a, vote["vote_id"], unit_id, str(option_ids[0])
    )
    assert first_response.status_code == 201

    second_response = await _cast_ballot(
        client, headers_b, vote["vote_id"], unit_id, str(option_ids[1])
    )

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_cast_ballot_concurrent_first_submissions_race_to_one_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    # A second client sharing the same FastAPI `app` (and therefore the same
    # get_session override, hence the same real Postgres testcontainer) as
    # `client`, so both requests race against the SAME database -- not two
    # independent in-memory fakes. Depending on real timing, the loser
    # surfaces as either ConcurrentBallotSubmissionError (DB partial-unique-
    # index violation on a true simultaneous insert) or
    # UnitAlreadyVotedByAnotherOwnerError (its own read already saw the
    # winner's committed ballot) -- both map to 409, so the *outcome* is
    # deterministic even though which specific error fires is not. This is
    # the API-level counterpart to the direct index test in
    # tests/integration/infrastructure/test_ballot_repository.py.
    community, headers_a, headers_b = await _create_community_with_two_owners_on_unit(
        client, auth_headers
    )
    vote = await _create_vote(client, headers_a, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
    ) as second_client:
        response_a, response_b = await asyncio.gather(
            _cast_ballot(
                client, headers_a, vote["vote_id"], unit_id, str(option_ids[0])
            ),
            _cast_ballot(
                second_client, headers_b, vote["vote_id"], unit_id, str(option_ids[1])
            ),
        )

    assert {response_a.status_code, response_b.status_code} == {201, 409}


@pytest.mark.asyncio
async def test_cast_ballot_precedence_ended_vote_wins_over_invalid_option_and_unit(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    # Both unit_id and option_id below are garbage -- if end_date weren't
    # checked before option/unit validation, this would surface as 404
    # (OptionDoesNotBelongToVoteError or UnitNotFoundInCommunityError), not
    # 409.
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    creator_account_id = await _register_account_id(
        client, f"vote-creator-{uuid4()}@example.com"
    )
    vote_id, _option_ids = await _insert_ended_vote(
        database_engine,
        community_id=community["id"],
        created_by_account_id=creator_account_id,
    )

    response = await _cast_ballot(
        client, voter_headers, str(vote_id), str(uuid4()), str(uuid4())
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cast_ballot_error_messages_are_pairwise_distinct(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    database_engine: AsyncEngine,
) -> None:
    # Guards against a future refactor silently merging the unified
    # authorization message with the option/unit "not found" messages --
    # OptionDoesNotBelongToVoteError and UnitNotFoundInCommunityError are
    # deliberately NOT unified with AccountNotAuthorizedToCastBallotError
    # (unlike community_id in CreateVote).
    community, voter_headers = await _create_community_with_voter(client, auth_headers)
    vote = await _create_vote(client, voter_headers, community["id"])
    unit_id = community["units"][0]["id"]
    option_ids = await _get_vote_option_ids(database_engine, vote["vote_id"])

    unauthorized_response = await _cast_ballot(
        client, auth_headers, vote["vote_id"], unit_id, str(option_ids[0])
    )
    unknown_option_response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], unit_id, str(uuid4())
    )
    unknown_unit_response = await _cast_ballot(
        client, voter_headers, vote["vote_id"], str(uuid4()), str(option_ids[0])
    )

    messages = {
        unauthorized_response.json()["detail"],
        unknown_option_response.json()["detail"],
        unknown_unit_response.json()["detail"],
    }
    assert len(messages) == 3
