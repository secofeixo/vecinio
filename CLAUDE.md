# CLAUDE.md — Vecinio: Homeowners Association Management

## Purpose of this file
Loaded automatically in every Claude Code session. Contains ONLY operational
rules and current invariants — what Claude Code needs to act correctly
*today*. It does NOT contain the reasoning behind past decisions, bug
post-mortems, or design history — that lives in `docs/adr/` (see
`docs/adr/README.md` for the index) and is read on demand, not every
session. If this file and the code disagree, the code wins and this file
needs fixing.

**Size budget**: keep this file under ~400 lines. If a new entry would push
past that, prune something first — see "Keeping this file lean" at the
bottom before adding narrative content.

## Tech stack
- **Backend**: Python 3.12+, FastAPI, async throughout (SQLAlchemy async +
  `postgresql+psycopg`, single driver — no `asyncpg`).
- **Package manager**: `uv`. `uv add <pkg>`, `uv run <cmd>`, `uv.lock`.
- **Persistence**: PostgreSQL. Migrations via Alembic (async template),
  `migrations/` is the single source of schema truth. Tests provision schema
  via real `alembic upgrade head`/`downgrade base` against testcontainers,
  never `Base.metadata.create_all` (ADR-0002).
- **Architecture**: Tactical DDD. No CQRS, no Event Sourcing (ADR-0003).
- **Auth**: JWT access tokens (~15 min) + opaque refresh tokens (hashed at
  rest, revocable). Password hashing: `pwdlib` + argon2id (ADR-0001).
- **Frontend**: Vue 3 (Composition API) + Pinia + Vuetify + `vue-router` +
  axios. JavaScript, not TypeScript (ADR-0012).
- **Testing**: pytest + pytest-asyncio (strict mode, explicit
  `@pytest.mark.asyncio`). Unit (no I/O) / integration (real Postgres via
  testcontainers) / e2e (httpx.AsyncClient, same testcontainers+alembic
  pattern, `app.dependency_overrides[get_session]`).
- **CI**: GitHub Actions, `lint` + `test` jobs run in parallel (not
  `needs: lint`), both `timeout-minutes: 15`. No frontend CI job yet.
- **Stub, not implemented**: `src/infrastructure/persistence/audit_log.py`
  and `src/infrastructure/outbox/outbox_repository.py` are empty. Do not
  assume they work.
- **Local dev DB**: `docker-compose.yml` runs Postgres on host port 5433,
  separate from the testcontainers instances tests spin up automatically.
  `docker compose down` when done with manual migration work.

## Bounded contexts implemented
- **community**: `Community` aggregate (units, CIF, address); `Unit` entity
  (participation coefficient, owner_ids, `identifier` unique per community).
- **owner**: `Owner` aggregate (NIF/NIE, email, phone — independent
  identity, no login).
- **identity**: `Account` aggregate (email, password_hash, optional
  `owner_id`) + `RefreshToken`. One `Account` per person, never a shared
  household login (traceability of who did what).
- **community_group**: `CommunityGroup` — Spanish "mancomunidad de
  propietarios". References `Community` by ID (`member_community_ids`),
  doesn't contain them. `slug` derived from `name`, UNIQUE. No exclusivity
  invariant between groups; no presidency concept yet.
- **quota**: `Quota` — snapshot split of an amount across a `Community`'s
  `Unit`s at a point in time. `total` is `@computed_field = sum(lines)`.
  `allocations` immutable snapshot per `Unit`, largest-remainder method
  (`src/domain/quota/allocation.py`, pure function). Creation only — no
  billing/payment/recalculation use case yet (`supersedes_quota_id` exists,
  unused). Overlap rule and its accepted race window: ADR-0011.
- **vote**: `Vote` + `Ballot` (separate aggregates) + `calculate_vote_result`
  (pure function). `Vote.close()` only guards double-close; deadline check
  lives in the `CloseVote` use case. `VoteResult` reports raw tallies only,
  never `approved: bool`. HTTP error-mapping conventions: ADR-0004.
  Check-order-as-tested-contract discipline: ADR-0005. `Ballot` DB
  constraint and a real bug fixed there: ADR-0006. JSONB persistence and a
  real bug fixed there: ADR-0007.

## `identity`/`owner` HTTP endpoints of note
- `GET /auth/me` — first protected read endpoint. Design rationale: ADR-0008.
- `POST /auth/me/link-owner` — NIF-only self-service linking, no identity
  verification (deliberate land-grab trade-off — do not harden without
  discussion, see "Do NOT do without asking"). Rationale: ADR-0009.
- `GET /owners/me/units` — first list endpoint in the project. Rationale:
  ADR-0010.

## Business invariants (do not reopen without explicit confirmation)
- `Owner` independent aggregate, 0..N communities.
- `Unit` is an entity INSIDE `Community` (not its own aggregate) — the
  "sum of participation coefficients = 100%" invariant needs transactional
  consistency.
- `Unit.owner_ids` is a tuple (co-ownership). Joint-and-several liability:
  each co-owner liable for 100% of dues, not split proportionally.
- `Unit.identifier` non-empty, unique within its Community
  (`DuplicateUnitIdentifierError` → 400, same-payload consistency check).
- CIF/NIF/NIE validation follows real Spanish checksum algorithms — do not
  simplify.
- `Account.owner_id ↔ Owner` is 1:1, enforced at DB level
  (`uq_accounts_owner_id`). Context: ADR-0009.
- `CommunityGroup.member_community_ids`: minimum 2, no duplicates, enforced
  on every mutation. `slug` never settable — always derived, UNIQUE
  constraint; empty-slug names rejected (`InvalidCommunityGroupNameError`).
- `CommunityGroup` presidency invariant is deliberately deferred — blocked
  on a `governance` bounded context that doesn't exist yet. Do not add a
  presidency check to `CommunityGroup` without `governance` existing first.
- Invariant validation lives in aggregate methods, NEVER in the router or
  use case. Every entry point (API, batch import, scheduled job) goes
  through the aggregate.
- **Optimistic concurrency**: `Community`, `Owner`, `Account`,
  `CommunityGroup`, `Quota`, `Vote` all carry `version: int`. `Ballot`
  deliberately does not (ADR-0006). Repository `save()` upserts with
  `WHERE version = <expected>`, detects a skipped update via `RETURNING`
  (not `rowcount` — unreliable with async psycopg on
  `ON CONFLICT ... WHERE`), raises `ConcurrentModificationError` → 412. Any
  new mutable aggregate needs this pattern unless it has its own dedicated
  concurrency mechanism.
- **IntegrityError handling**: any `save()` that can hit a DB UNIQUE
  constraint must catch `IntegrityError`, `await session.rollback()`
  unconditionally FIRST in the `except` block, then inspect
  `error.orig.diag.constraint_name` (not string-matching the message).
- Login and any "does this identifier exist" check return an IDENTICAL
  error/message for "not found" vs. "wrong credential" — never let a caller
  distinguish them (enumeration oracle). General convention: ADR-0004.
- `Quota` ordinary-period overlap check and its accepted race window:
  ADR-0011.
- `Vote` counts as "open" purely on `result is None`, regardless of
  `end_date`. `Unit` coefficient/membership changes must be blocked while
  any `Vote` of that `Community` is open — mechanism
  (`VoteRepository.exists_open_vote_for_community`) exists and is tested,
  but **no use case wires it in yet** (no use case currently changes an
  existing `Unit`'s coefficient or a Community's unit count —
  `AssignOwnerToUnit` only touches `owner_ids`). Do NOT create
  `CommunityHasOpenVoteError` or inject `VoteRepository` into any use case
  until an actual subdivision/coefficient-change use case is built.

## Coding conventions
- Entities/VOs/Aggregates are `pydantic.BaseModel` (`frozen=True`);
  mutating aggregate roots use `validate_assignment=True` PLUS
  `Field(frozen=True)` on individual immutable fields —
  `validate_assignment=True` alone does NOT block reassignment, it only
  re-runs validators.
- Repositories: ABC interfaces in `domain/`, implementations in
  `infrastructure/`. All methods `async def`.
- One use case = one class, one `execute()` method. Domain exceptions
  propagate through use cases unchanged — never caught/re-wrapped/swallowed.
- Domain IDs are typed Value Objects, never bare `str`/`UUID` crossing
  layers — EXCEPT at the use case `execute()` boundary, which takes raw
  primitives and constructs VOs internally. Narrow exception:
  `CreateQuota.execute()` takes the `QuotaType` enum directly (already
  validated at the HTTP/Pydantic boundary).
- `vote` use cases take an injected `now: datetime` — never call
  `datetime.now()` internally.
- Each `vote` use case defines its OWN local copies of shared-sounding
  errors (`AccountNotFoundError`, etc.) rather than importing from one
  another — consistent, deliberate duplication project-wide. Do not
  "clean this up" without discussing it first.
- Everything (concepts, aggregates, events, use cases, comments, variable
  names) is in English, except `CIF`/`NIF`/`NIE` (no English equivalent).
- Cross-aggregate existence checks belong in the application-layer use
  case, never inside the aggregate — an aggregate can only validate itself.
- Every FastAPI route sets `summary`, English `description`, explicit
  `response_model`, and `responses={...}` for every domain-error status it
  can return. This is the sole source of API documentation (no hand-written
  docs files). Error-mapping conventions: ADR-0004.

## Commands
- Install: `uv sync` · Add dep: `uv add <package>`
- Unit tests: `uv run pytest tests/unit`
- Integration tests: `uv run pytest tests/integration` (Docker required)
- E2E tests: `uv run pytest tests/e2e` (Docker required)
- Full suite: `uv run pytest tests`
- Run API: `uv run uvicorn src.interfaces.api.main:app --reload` (needs
  `DATABASE_URL`, `JWT_SECRET_KEY`)
- New migration: `uv run alembic revision --autogenerate -m "description"` —
  ALWAYS read the generated file against the actual models before trusting
  it (autogenerate has been wrong before: missing constraints, wrong
  precision). For a `postgresql_where` partial index, ALSO verify the DDL
  directly in `psql` (`\d <table>`) — autogenerate can silently produce a
  full index instead of a partial one.
- Apply migrations: `uv run alembic upgrade head`
- Pre-commit (all hooks): `uv run pre-commit run --all-files` — NOTE:
  `.pre-commit-config.yaml` excludes `^migrations/`, so no hook has ever
  checked any file under `migrations/versions/`. Known, accepted gap.
- Frontend dev server: `cd frontend && npm run dev` (port 5173; needs
  backend + `docker compose up -d db` running too)
- Frontend unit tests: `npm run test:unit` (Vitest)

## Frontend — current state
Landing screen is "Mis viviendas" (`MyUnitsView.vue`, consumes
`GET /owners/me/units`), not community creation. "Vincular propietario"
(`LinkOwnerView.vue`) reachable only from that screen's 404/no-linked-owner
state. Screen-level UX decisions: ADR-0013. Stack decisions: ADR-0012.

- No community/vote list endpoints exist — only `GET /communities/{id}` and
  `GET /communities/{id}/quotas/{id}` (by id). No "browse all my
  communities" screen possible yet.
- Units can only be created inline as part of `POST /communities` — no
  standalone "add a unit to an existing community" endpoint, hence the
  combined community+units form.
- CORS hardcoded to Vite's local dev ports — must become environment-driven
  before real deployment.

## Domain purity exception: pydantic
`domain/` uses `pydantic.BaseModel` for Entities/VOs/Aggregates — accepted
exception to "pure Python domain" for declarative validation,
immutability/hashability, free JSON serialization at the boundary. Applies
ONLY to pydantic, not ORMs, HTTP clients, or any other infra-flavored
library. Any other proposed domain dependency needs its own trade-off
discussion first.

## Do NOT do without asking
- Do not introduce CQRS, Event Sourcing, or a second database (ADR-0003).
- Do not add dependencies to `domain/` beyond pydantic without discussing
  the trade-off first.
- Do not add `asyncpg` — single driver is `psycopg` (async).
- Do not use `passlib` — replaced by `pwdlib` (ADR-0001).
- Do not create `CommunityHasOpenVoteError` or wire `VoteRepository` into
  any `community` use case until a subdivision/coefficient-change use case
  actually exists.
- Do not make `CastBallot` catch/retry on `ConcurrentBallotSubmissionError`
  without discussing the project-wide retry strategy first (ADR-0011).
- Do not add identity verification to `POST /auth/me/link-owner` without
  discussing the approach first — current NIF-only behavior is a deliberate
  trade-off, not an oversight (ADR-0009).

## Keeping this file lean
- **This file = operational rules only.** No "why we chose X over Y" essays,
  no bug post-mortems, no design-meeting narrative. If you're about to write
  more than 2-3 sentences justifying a decision, that justification belongs
  in a new ADR (`docs/adr/NNNN-title.md`, see `docs/adr/README.md`) —
  leave only the resulting rule + a link here.
- **When a bounded context or feature moves from "in progress" to "closed
  and covered by tests"**, compress its section here to invariants only;
  move the process/rationale narrative to an ADR if it isn't already one.
- **Size budget is ~400 lines.** If adding something would exceed it, prune
  or move something to an ADR in the same edit — don't let the file grow
  unchecked. Do not prune automatically/silently: propose the specific ADR
  split to the human and get confirmation before deleting content from this
  file, since some "narrative" here encodes real, still-relevant trade-offs
  (e.g. the NIF land-grab decision) that must not be lost by a heuristic
  that can't tell the difference between noise and a security decision.

# Session-digest file
Read `.claude/session_digest.md` for product decisions not yet implemented
in code.
