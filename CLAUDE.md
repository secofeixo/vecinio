# CLAUDE.md — Vecinio: Homeowners Association Management

## Purpose of this file
Loaded automatically in every Claude Code session. Contains ONLY what Claude Code
would otherwise need to discover by reading code or asking — not product docs.
Kept in sync with the actual codebase; if this file and the code disagree, the
code wins and this file needs fixing.

## Tech stack
- **Backend**: Python 3.12+, FastAPI, async throughout (SQLAlchemy async +
  `postgresql+psycopg` driver — single driver, do not add asyncpg alongside it).
- **Package manager**: `uv` (not poetry, not pip directly). `uv add <pkg>`,
  `uv run <cmd>`, lockfile is `uv.lock`.
- **Persistence**: PostgreSQL. Migrations via **Alembic** (async template),
  `migrations/` — the single source of schema truth. Integration/e2e tests
  provision schema via `alembic upgrade head`/`downgrade base` against a
  testcontainers Postgres instance, NOT `Base.metadata.create_all` — this was a
  deliberate switch made once Alembic was introduced, to avoid two schema
  sources drifting apart.
- **Architecture**: Tactical DDD (no CQRS, no Event Sourcing — deliberately
  rejected; see invariants below).
- **Auth**: JWT access tokens (short-lived, ~15 min) + opaque refresh tokens
  (long-lived, hashed at rest, revocable). Password hashing via `pwdlib` +
  argon2id (NOT passlib — unmaintained, compatibility warnings with modern
  bcrypt; NOT bcrypt directly — 72-byte silent truncation footgun that argon2id
  doesn't have).
- **Frontend**: Vue 3 (Composition API) + Pinia — not started yet.
- **Testing**: pytest + pytest-asyncio (strict mode, explicit `@pytest.mark.asyncio`,
  no `asyncio_mode = auto` configured). Unit (no I/O) / integration (real Postgres
  via testcontainers) / e2e (httpx.AsyncClient against the FastAPI app, same
  testcontainers+alembic pattern, session overridden via
  `app.dependency_overrides[get_session]`).
- **CI**: GitHub Actions (`.github/workflows/ci.yml`), two parallel jobs —
  `lint` (`pre-commit run --all-files`) and `test` (`pytest tests/unit
  tests/integration tests/e2e`, needs Docker for testcontainers). Both have
  `timeout-minutes: 15`. Jobs run in parallel by deliberate choice (not
  `needs: lint`) — trade-off accepted: faster feedback over saving CI minutes.
- **Not yet implemented, despite folders existing**: `src/infrastructure/persistence/audit_log.py`
  and `src/infrastructure/outbox/outbox_repository.py` are still empty stub
  files. Domain events + outbox pattern were the plan for future audit/integration
  needs but have not been built. Do not assume they work.

## Bounded contexts implemented so far
- **community**: `Community` aggregate (units, CIF, address), `Unit` entity
  (participation coefficient, owner_ids, `identifier` — human-readable label like
  "4º-2ª", required + non-empty, unique per community).
- **owner**: `Owner` aggregate (NIF/NIE, email, phone — independent identity,
  no login).
- **identity**: `Account` aggregate (email, password_hash, optional `owner_id`
  link) + `RefreshToken`. Separate bounded context from `owner` — an Account is
  a login credential, an Owner is a legal/business identity; they are linked by
  ID, never merged. **Decision**: one Account per person (co-owners each get
  their own Account + Owner + NIF), not a single shared "family" login — chosen
  for traceability of who did what.
- **community_group**: `CommunityGroup` aggregate — Spanish legal figure
  "mancomunidad de propietarios" (LPH), e.g. two communities like "206" and
  "208" that share certain governance bodies. References member `Community`
  aggregates by ID (`member_community_ids`), does NOT contain them — each
  `Community` keeps its own transactional 100%-coefficient invariant.
  Independent aggregate, own bounded context. `slug` is a computed property
  derived from `name` (not stored input), persisted with a UNIQUE constraint.
  **Decision**: no exclusivity invariant between groups — a `Community` can
  belong to more than one `CommunityGroup` at the same time, deliberately;
  the LPH does not impose exclusivity on mancomunidad membership, so nothing
  in the domain prevents it. No governance/presidency concept exists yet
  (see the presidency-invariant bullet under "Business invariants" below).
- **quota**: `Quota` aggregate — a snapshot split of an amount across a
  `Community`'s `Unit`s at a point in time (`period_start`/`period_end`,
  `type` = `ordinary`/`extraordinary`). `lines` (concept + `Decimal` amount,
  no sign restriction) drive `total`, a `@computed_field` derived as
  `sum(lines)` — never an independent input, same pattern as
  `CommunityGroup.slug`. `allocations` is an immutable snapshot, one
  `QuotaAllocation` per `Unit` existing in the `Community` at creation time
  (`unit_id`, `participation_coefficient`, `amount` — all frozen values, never
  recalculated against current `Unit` state). Allocation uses the
  **largest-remainder method** (`src/domain/quota/allocation.py`,
  `allocate_largest_remainder`, a pure function, not a `Quota` method — kept
  standalone because building it requires reading all of a `Community`'s
  current units, a cross-aggregate concern). **Increment scope**: creation
  only — no billing, payment/periodicity, or the recalculation/superseding
  use case yet; `supersedes_quota_id` exists on the model but nothing sets or
  reads it.

## Business invariants already decided (do not reopen without explicit confirmation)
- `Owner` is an independent aggregate (own identity, can belong to 0..N communities).
- `Unit` is an entity INSIDE the `Community` aggregate (not its own aggregate),
  because the invariant "sum of participation coefficients of all units = 100%"
  requires transactional consistency.
- `Unit.owner_ids` is a tuple (co-ownership supported). JOINT AND SEVERAL liability:
  each co-owner is liable for 100% of that unit's dues; liability is NOT split
  proportionally.
- `Unit.identifier` must be non-empty and unique within its Community
  (`DuplicateUnitIdentifierError`, mapped to HTTP 400 — a same-payload
  consistency check, not a conflict with persisted state, hence 400 not 409,
  consistent with the existing duplicate-unit-id check).
- CIF/NIF/NIE validation follows the real Spanish checksum algorithms (verified
  against official sources during implementation — do not "simplify" these).
- `CommunityGroup.member_community_ids` requires a minimum of 2 members, no
  duplicates, enforced on every mutation (`add_member`/`remove_member`), not
  just at construction. `slug` is NEVER a settable field — always derived from
  `name` (NFKD-normalize, strip Unicode category `Mn`, lowercase, non
  `[a-z0-9]` chars → `-`, collapse/trim hyphens) and persisted with a UNIQUE
  DB constraint; a `name` that normalizes to an empty slug is rejected
  (`InvalidCommunityGroupNameError`).
- `CommunityGroup` has no membership-exclusivity invariant (see
  "community_group" above) and no presidency invariant. The presidency rule
  ("the mancomunidad's president must be president of one of its member
  communities") is a deliberately deferred cross-aggregate application-layer
  check — it cannot live inside `CommunityGroup` itself, since an aggregate
  can only validate itself, not query another `Community`'s presidency.
  Blocked on a `governance` bounded context that doesn't exist yet (no
  president/role concept anywhere in the domain today) — do not add a
  presidency check to `CommunityGroup` without `governance` existing first.
- Invariant validation lives in aggregate methods, NEVER in the FastAPI router
  or the use case. Every entry point into the system (API, batch import,
  scheduled job) must go through the aggregate.
- **Optimistic concurrency**: `Community`, `Owner`, `Account`,
  `CommunityGroup`, and `Quota` all carry a `version: int` field. Repository `save()` does an upsert with
  `WHERE <table>.version = <expected_version>`, detects a skipped update via
  `RETURNING` (NOT `rowcount` — unreliable/`-1` with async psycopg on
  `ON CONFLICT ... WHERE`), and raises a per-aggregate `ConcurrentModificationError`
  (mapped to HTTP 412) if the version doesn't match. Any new mutable aggregate
  needs this same pattern.
- **IntegrityError handling**: any repository `save()` that can hit a DB-level
  UNIQUE constraint must catch `IntegrityError`, call `await session.rollback()`
  UNCONDITIONALLY as the first statement in the `except` block (before either
  raise path — an uncommitted DBAPI error leaves the connection aborted until
  rolled back), then inspect `error.orig.diag.constraint_name` (not string-matching
  the message) to decide whether to translate to a domain error or re-raise.
- Login (`InvalidCredentialsError`) and any future "does this identifier exist"
  check must return the IDENTICAL error/message for "not found" and "wrong
  credential" cases — never let a caller distinguish them, or it becomes an
  enumeration oracle.
- An ordinary `Quota`'s period must not overlap another ordinary `Quota` of
  the SAME `Community` (inclusive on both bounds — a shared boundary day,
  e.g. one ending 2026-12-31 and another starting 2026-12-31, counts as
  overlapping). Checked in the `CreateQuota` use case via
  `QuotaRepository.exists_overlapping_ordinary` (an aggregate can only
  validate itself, not query other persisted `Quota` rows), raising
  `OverlappingOrdinaryQuotaError` (HTTP 400). `extraordinary` quotas are never
  checked against anything — they can freely coexist with any other quota,
  ordinary or extraordinary, same or different period.
  **Deliberate exception to the project's DB-guaranteed-uniqueness pattern**
  (`Unit.identifier`, `CommunityGroup.slug`): this overlap invariant is
  backed only by a plain (non-unique) index on `(community_id, type,
  period_start, period_end)` for query efficiency, NOT by a DB-level
  uniqueness/exclusion constraint. Two concurrent `POST` requests creating
  overlapping ordinary quotas for the same community can both succeed (an
  accepted race window) — accepted given expected write volume (ordinary-quota
  creation is at most an annual event per community). If write volume ever
  grows enough to matter, the correct fix is a Postgres `EXCLUDE` constraint
  using the `btree_gist` extension, not tightening the use-case check alone.

## Coding conventions
- Value Objects/Entities/Aggregates are immutable-by-default pydantic
  `BaseModel` (`frozen=True`); aggregate roots that mutate use
  `validate_assignment=True` instead of `frozen=True` (see pydantic exception
  below).
- Repositories are defined as interfaces (ABC) in `domain/`, implemented in
  `infrastructure/`. All repository methods are `async def`.
- One use case = one class with a single `execute()` method. Do not merge two
  use cases into one handler. Domain exceptions propagate through use cases
  unchanged — never caught/re-wrapped/swallowed there.
- Domain IDs are typed Value Objects (`CommunityId`, `OwnerId`, `AccountId`,
  etc.), never a bare `str` or `UUID` crossing layers — EXCEPT at the
  application-layer `execute()` boundary, which takes raw primitives (str,
  UUID, Decimal) and constructs Value Objects internally, mirroring
  `RegisterCommunity`'s convention. Narrow exception: `CreateQuota.execute()`
  takes `type: QuotaType` (the enum itself), not `str` — the Pydantic API
  schema (`CreateQuotaRequest.type: QuotaType`) already validates it at the
  HTTP boundary (FastAPI returns 422 on an invalid value), so there is no
  primitive-to-domain conversion left for the use case to do.
- Everything — domain concepts, aggregates, events, use cases, comments,
  variable names — is in English. Exceptions: `CIF` and `NIF`/`NIE` (Spanish
  legal identifiers with no English equivalent) keep their original names.
- Cross-aggregate existence checks (e.g. "does this Owner exist before linking
  it") belong in the application-layer use case, never inside the aggregate
  itself — an aggregate can only validate itself, not query other aggregates'
  repositories.

## Commands
- Install dependencies: `uv sync`
- Add a dependency: `uv add <package>`
- Unit tests: `uv run pytest tests/unit`
- Integration tests: `uv run pytest tests/integration` (requires Docker; uses
  testcontainers + real Alembic migrations)
- E2E tests: `uv run pytest tests/e2e` (requires Docker)
- Full suite: `uv run pytest tests`
- Run local API: `uv run uvicorn src.interfaces.api.main:app --reload`
  (requires `DATABASE_URL` and `JWT_SECRET_KEY` env vars set)
- New migration: `uv run alembic revision --autogenerate -m "description"` —
  ALWAYS read the generated file and verify it against the actual model
  definitions before trusting it; autogenerate has been wrong before
  (missing constraints, wrong precision).
- Apply migrations: `uv run alembic upgrade head`
- Pre-commit (all hooks, forced): `uv run pre-commit run --all-files`
- **Note**: `.pre-commit-config.yaml` has `exclude: ^migrations/` — this means
  NO hook (black, isort, flake8, mypy, pydocstyle, complexipy, detect-secrets)
  has ever actually checked any file under `migrations/versions/`, for any
  migration, ever. This is a known, accepted gap, not yet revisited.

## Domain purity exception: pydantic
`domain/` uses `pydantic.BaseModel` for Entities, Value Objects, and Aggregates.
Deliberate, accepted exception to "pure Python domain" — for declarative
validation, immutability/hashability, and free JSON serialization at the
`interfaces/` boundary. Trade-off accepted knowingly: pydantic controls the
validation lifecycle instead of the developer deciding explicitly when each
rule fires — this is less control, not more flexibility; don't cite
"flexibility" as the reason if revisited. Applies ONLY to pydantic — does not
extend to ORMs, HTTP clients, or any other infrastructure-flavored library.
Any other proposed domain dependency needs the same explicit trade-off
discussion.

## Do NOT do without asking
- Do not introduce CQRS, Event Sourcing, or a second database.
- Do not add dependencies to `domain/` beyond pydantic without discussing the
  specific trade-off first.
- Do not touch `frontend/` yet — out of scope until the backend has stable use
  cases covering more of the real domain (quotas, incidents, votes).
- Do not add `asyncpg` — the project standardized on `psycopg` (async) as the
  single Postgres driver.
- Do not use `passlib` for anything — unmaintained, already replaced by
  `pwdlib`.