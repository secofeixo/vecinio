# ADR-0010: `GET /owners/me/units` — first list endpoint

## Status
Accepted, implemented.

## Decisions
- New abstract method `find_by_owner_id(owner_id) -> tuple[Community, ...]`
  on `CommunityRepository`, implemented via
  `UnitModel.owner_ids.any(owner_id.value)` (Postgres `ANY()`). Deliberately
  returns full `Community` aggregates (including units NOT owned by the
  queried owner) — router filters down afterward. Chosen over a leaner SQL
  projection specifically to keep "repositories always return whole
  aggregates" intact; a projection would have been the first case breaking
  it.
- No GIN index added on `units.owner_ids` — same accepted-trade-off pattern
  as the `Quota` overlap check (ADR-0011): not needed at today's scale, not
  added speculatively.
- `account.owner_id → Owner` resolution NOT reused from `GET /auth/me`
  (ADR-0008), NOT extracted into a shared dependency — considered and
  rejected. `GET /auth/me` treats `owner_id is None` as valid (200,
  `owner: null`); this endpoint must reject it (404) — same check, different
  failure semantics. This endpoint also never loads the `Owner` aggregate at
  all — only needs the `OwnerId` value to pass into `find_by_owner_id`; the
  FK guarantees a non-null `owner_id` points at a real row.
- New exception `OwnerNotLinkedToAccountError`, defined directly in the
  router file, not in `domain/identity/` — `account.owner_id is None` is a
  valid `Account` state, not an aggregate invariant violation. First
  domain-shaped exception defined inside a router rather than a use case
  module (consequence of no read-only use case classes existing).
- First list endpoint: `response_model=list[OwnerUnitResponse]`, bare JSON
  array, no pagination. Embeds `community_name`/`community_address`
  (importing `AddressResponse` from `community_schemas.py`) rather than just
  `community_id`, since no community-listing endpoint exists yet.
- Route declared `GET /owners/me/units`, positioned before any future
  `GET /owners/{owner_id}` — FastAPI matches routes in declaration order, so
  `/{owner_id}` would swallow `/me` if declared first. Flagged inline in the
  router.
