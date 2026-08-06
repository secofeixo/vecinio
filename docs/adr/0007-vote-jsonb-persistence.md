# ADR-0007: `Vote.options`/`Vote.result` stored as JSONB

## Status
Accepted, implemented.

## Decision
`votes` table stores `options` and `result` as JSONB (first JSONB usage in
the project), serialized via pydantic `model_dump(mode="json")` /
`model_validate` — chosen over relational child tables because both are
effectively immutable-once-written blobs with no need for independent SQL
querying (`options` fixed at creation, `result` written once atomically at
`CloseVote`).

`Decimal` fields inside (`weighted_coefficient`,
`total_participation_coefficient`) survive the round trip with full
precision because pydantic's `mode="json"` serializes `Decimal` as a string,
not a float — verified with an 18-digit test case.

`ballots` table stays fully relational (not JSONB) since it's exactly what
the partial unique index (ADR-0006) needs to enforce.

## Bug found and fixed: `none_as_null`
The `result` JSONB column needed `JSONB(none_as_null=True)`. Without it,
SQLAlchemy's default JSON/JSONB bind processor writes a Python `None` as the
JSON literal `null` rather than SQL `NULL`, which silently broke
`WHERE result IS NULL` (used by `exists_open_vote_for_community`) — the
query returned zero rows for a genuinely open vote.

Caught by an integration test against real Postgres, not by unit tests (a
fake repository wouldn't hit this bind-processor behavior at all) — this is
the concrete argument for why `vote`'s integration suite exists and uses
testcontainers+Alembic rather than trusting fakes alone (see ADR-0002).

## Consequences
Any future JSONB column that can legitimately be NULL and is queried with
`IS NULL` must use `JSONB(none_as_null=True)` — this is easy to miss and
won't fail unit tests.
