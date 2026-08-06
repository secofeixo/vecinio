# ADR-0002: Integration/e2e tests provision schema via Alembic, not `Base.metadata.create_all`

## Status
Accepted, implemented.

## Decision
Integration and e2e tests provision schema by running real Alembic migrations
(`alembic upgrade head` / `downgrade base`) against a testcontainers Postgres
instance — not `Base.metadata.create_all`.

## Rationale
Deliberate switch made once Alembic was introduced, to avoid two schema
sources (the ORM models and the migration files) silently drifting apart.
`Base.metadata.create_all` would validate the models but not that the actual
migration files produce the same schema.

## Consequences
- Slower test setup than `create_all`, accepted trade-off.
- Any new migration must actually be runnable via `alembic upgrade head` for
  tests to pass — this is enforced, not just aspirational.
