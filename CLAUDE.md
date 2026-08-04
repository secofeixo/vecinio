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
- **Frontend**: Vue 3 (Composition API) + Pinia. Started — see the "Frontend"
  section below for the full stack and conventions.
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
- **Local dev DB**: `docker-compose.yml` runs a Postgres service (`db`, port
  5433 on the host) for manual/local work (e.g. running `alembic
  revision --autogenerate` by hand). This is separate from the testcontainers
  Postgres instances spun up automatically by integration/e2e tests — don't
  confuse the two, and don't leave the docker-compose `db` container running
  after manual migration work (`docker compose down` when done).

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
- **vote**: community consultations/votes (approve a budget, a special levy,
  a solar-panel study, etc.). Two aggregates plus one pure calculation
  function:
  - `Vote` (aggregate root, `validate_assignment=True`): `community_id`,
    `title`, `description`, `options: tuple[VoteOption, ...] = Field(frozen=True)`
    (minimum 2, unique labels, fixed at creation — a `Vote` cannot add/remove
    options later), `end_date`, `created_by_account_id`, `result:
    VoteResult | None = None` (the only mutable field besides `version`),
    `version: int = 0`. Built via `Vote.create(..., now: datetime)` — `now` is
    an injected clock parameter (not a stored field), needed because
    `end_date` must be strictly in the future only *at creation time*
    (`VoteEndDateNotInFutureError`); a stored past-dated `Vote` rehydrated
    from persistence must NOT re-fail this check on load, hence it lives in
    `create()`, not in the `model_validator`. `close(result: VoteResult)`
    sets `result` once; raises `VoteAlreadyClosedError` on a second call —
    this is the aggregate's own invariant (never cerrar dos veces); whether
    `end_date` has actually passed is checked by the `CloseVote` use case,
    not by the aggregate.
  - `VoteOption` (frozen VO): `id: VoteOptionId`, `label: str` (non-empty).
  - `Ballot` — **its own aggregate**, not an entity inside `Vote` (needed a
    DB-level `UNIQUE` constraint for concurrency safety, incompatible with
    living inside `Vote`'s transactional boundary). Fields:
    `id, vote_id, unit_id, option_id, cast_by_owner_id, cast_at` all
    `Field(frozen=True)`; `superseded_by_ballot_id: BallotId | None = None`
    is the ONLY mutable field. `Ballot.create(..., now: datetime)` sets
    `cast_at=now`. `supersede(by: BallotId)`: checks `by == self.id` first
    (`BallotCannotSupersedeItselfError`, checked before the next one because
    it's a more fundamental error, independent of current state), then
    checks `self.superseded_by_ballot_id is not None`
    (`BallotAlreadySupersededError`). **Decision**: a unit's ballot can only
    be corrected (superseded) by the SAME owner who originally cast it — a
    different co-owner of the same `Unit` cannot override it (this is
    enforced by the `CastBallot` use case, not the aggregate, since it
    requires comparing against the existing ballot — a cross-aggregate
    concern).
  - `VoteResult` + `OptionTally` (frozen VOs, embedded inside `Vote.result`,
    not their own aggregate/table — no independent lifecycle, created whole
    at `CloseVote` time): `OptionTally` = `option_id, unit_count,
    weighted_coefficient` (raw summed `Decimal`, NOT a pre-computed
    percentage — same convention as `Quota` storing `amount` rather than a
    derived `percentage_of_total`). `VoteResult` = `tallies` (ALWAYS one
    entry per `Vote.options`, including options with zero votes —
    `unit_count=0`, `weighted_coefficient=Decimal("0")` — a real bug was
    caught and fixed here: the first implementation silently dropped
    zero-vote options from `tallies`), `total_units_in_community`,
    `units_that_voted`, `total_participation_coefficient`, `closed_at`.
  - `calculate_vote_result` (`src/domain/vote/calculation.py`) — pure
    function, not a `Vote`/`VoteResult` method, same pattern as
    `allocate_largest_remainder` in `quota` (needs `Community.units` and all
    of a `Vote`'s `Ballot`s, both cross-aggregate reads). Only considers
    ballots with `superseded_by_ballot_id is None` (raises
    `InconsistentBallotStateError` if more than one active ballot exists for
    the same unit — should be impossible given the DB partial-unique
    constraint, but the pure function doesn't assume it). Raises
    `BallotReferencesUnknownUnitError` (not a raw `KeyError`) if an active
    ballot's `unit_id` isn't found in the given `units`.
  - **Decision**: a `Vote` reports raw tallies only — unit-count basis AND
    coefficient-weighted basis, side by side — never an `approved: bool`
    verdict. LPH majority thresholds (simple/qualified/unanimous, per
    decision type) are a future concern, deliberately out of scope; humans
    interpret the numbers against the meeting's actual agenda.
  - **Decision**: participation counts a `Unit` once it has ANY active
    ballot, including an explicit "abstención" option if the `Vote` defines
    one — abstaining counts as participating. A `Unit` that never casts any
    ballot does NOT count toward `units_that_voted`, only toward
    `total_units_in_community`.
  - **Decision**: ballot content (which option was chosen) is secret until
    `CloseVote`. Participation (which units HAVE voted, regardless of what)
    is public at all times — this is why `Ballot`'s existence-per-unit is
    queryable independently of `VoteResult`.

## `vote` HTTP interface — error-mapping conventions
Built across three routers: `POST /communities/{community_id}/votes`
(`CreateVote`), `POST /votes/{vote_id}/ballots` (`CastBallot`), `POST
/votes/{vote_id}/close` (`CloseVote`). `CastBallot`/`CloseVote` deliberately
do NOT nest under `/communities/{community_id}/...` — neither use case takes
a `community_id` (it's derived internally from `vote.community_id`), and
adding it to the path would require a new validation ("does this `vote_id`
belong to this `community_id`") that doesn't exist and shouldn't be added
just for URL aesthetics.

- **Non-enumeration via unified 404 bodies**: same principle already used
  for login (`InvalidCredentialsError`), now generalized to any check of the
  shape "does X exist AND do you have access to it" — both branches return
  the IDENTICAL response body, not just the same status code, precisely
  because a differentiated message on "existence" vs. "membership" turns
  the endpoint into an enumeration oracle for whichever identifier is
  sensitive.
  - `CreateVote`: `CommunityNotFoundError` and
    `AccountNotAuthorizedToCreateVoteError` → 404, body `{"detail":
    "Community not found or you are not a member of it"}`.
  - `CastBallot`: `AccountNotAuthorizedToCastBallotError` covers TWO
    distinct causes internally (account has no linked `owner_id`; owner
    doesn't own the requested `unit_id`) unified under one 404 body:
    `{"detail": "Not authorized to cast a ballot for this unit"}`.
  - `CloseVote`: same pattern, its own text: `{"detail": "Not authorized to
    close this vote"}`.
  - **Deliberate exception, NOT unified**: `UnitNotFoundInCommunityError` in
    `CastBallot` stays differentiated from the authorization 404 above —
    i.e. a caller CAN tell "this unit doesn't exist in this community" apart
    from "this unit exists but isn't yours". Accepted because `unit_id`
    never appears in any URL of this bounded context (only inside request
    bodies), unlike `community_id`, which is exposed in the path of `POST
    /communities/{community_id}/votes` and could leak through shared links
    between neighbors — that exposure asymmetry, not a general claim that
    "unit_id is less sensitive", is the actual reason. If this stops being
    true (e.g. `unit_id` starts appearing in a URL somewhere), revisit.
  - Any handler backing a unified message must use a **fixed string,
    ignoring `str(exc)`** — confirmed necessary the hard way: the same
    exception type raised from inside an aggregate method (which
    interpolates a pydantic Value Object into the f-string, e.g. `Vote`'s
    own `id: VoteId`) renders differently from the same exception raised
    from an application-layer use case (which interpolates a raw `UUID`
    parameter) — `Vote.close()` vs. `CloseVote.execute()` producing
    `"Vote value=UUID('...')  has already been closed"` vs. `"Vote ...
    has already been closed"` for the literal same error is the concrete
    example that surfaced this. Never wire a precedence-sensitive test's
    assertion to `str(exc)` without first printing both call sites' actual
    output side by side.

- **Check-order precedence is a tested contract, not an implementation
  detail.** Every use case's internal `if`/`raise` sequence determines which
  error a request with multiple simultaneous problems gets — this has to be
  pinned down explicitly (with its own e2e test per non-obvious ordering),
  not left for whoever refactors the use case later to notice or not.
  Confirmed orderings (see `tests/e2e/api/test_votes.py` for the actual
  assertions):
  - `CreateVote`: account exists → account has linked owner → community
    exists → owns a unit in it → **then** `Vote.create()` runs (so a
    malformed vote payload against a nonexistent/foreign community still
    returns 404, never 400 — the membership check wins).
  - `CastBallot`: vote exists → vote hasn't ended → account exists →
    account has linked owner → **option belongs to vote** → community
    exists (theoretical) → unit exists in community → **owner owns this
    unit**. The two most counter-intuitive rows: an ended vote wins over a
    garbage `unit_id`/`option_id` (409, not 404); and the option-membership
    check (same exception family, different cause) is checked BEFORE the
    "do you own this unit" check, even though both eventually map to the
    same unified 404 body when they're the auth-shaped one.
  - `CloseVote`: **reordered deliberately** during this work — `vote.result
    is not None` (→ `VoteAlreadyClosedError`) is now checked in
    `CloseVote.execute()` itself, BEFORE the `end_date` check (→
    `VoteHasNotEndedYetError`), even though `Vote.close()` also still
    guards the same thing internally (kept as-is, this is a deliberate
    duplication — the aggregate protects itself regardless of which use
    case calls it; the use case additionally short-circuits to give the
    right precedence at the HTTP boundary). Before this change, a
    (today-unreachable-via-normal-HTTP-flow, only-via-repository-bypass)
    vote that was already closed but whose `end_date` hadn't arrived yet
    would have returned "has not ended yet" instead of "already closed" —
    rejected as the wrong contract.

- **Theoretical/unreachable errors get documented, never silently dropped,
  and never tested if testing them means bypassing the domain on purpose**:
  - `AccountNotFoundError` (all three use cases) → 401, defense-in-depth
    only. `get_current_account` already rejects a JWT for a deleted account
    before any use case runs; this exception's only real reachability
    window is the (currently accepted) gap between the dependency's read
    and the use case's own `account_repository.get_by_id()` re-read of the
    same account — same class of accepted race window as `Quota` overlap
    checks elsewhere in the project. No e2e test for this; covered by the
    use case's own unit test instead.
  - `CommunityNotFoundError` raised from inside `CastBallot`/`CloseVote`
    (as opposed to the one in `CreateVote`, which comes from client input)
    means a persisted `Vote` points at a `Community` that no longer exists
    — a data-integrity problem, not a client error → 500 + `logger.error`,
    NOT 404 (a 404 here would misleadingly imply "fix your request").
    Confirmed via `grep` that no delete-Community mechanism exists anywhere
    in the codebase today (the only near-miss hit is
    `remove_community_from_group`, which only unlinks a `Community` from a
    `CommunityGroup`, never deletes the aggregate) — so this is phrased as
    "no mechanism exists today", not as a designed-in invariant that
    communities can never be deleted. No test for this case; the omission
    is documented with an inline comment in `test_votes.py`, same pattern
    already used in `test_assign_owner_to_unit.py` for the untested 412
    scenario there.

- **`ConcurrentBallotSubmissionError`/`ConcurrentModificationError` (409/412)
  have no automatic retry anywhere in the project, `vote` included.** This
  is flagged as an OPEN, project-wide design question, not a closed decision
  local to any one endpoint: whether/how a router should retry once, surface
  a plain 409, or something else, on a concurrency collision hasn't been
  decided, and shouldn't be solved ad hoc for a single endpoint without
  discussing the general strategy first. `POST /votes/{vote_id}/close`'s
  `responses={412: ...}` docstring says this explicitly — mirror that
  wording if this comes up again elsewhere before the general strategy is
  designed.

- **No logging configuration exists anywhere in the project.** The first
  `logger = logging.getLogger(__name__)` in the codebase was added as part
  of this work (for the `CommunityNotFoundError` 500 case above). There is
  no `logging.basicConfig`, no `dictConfig`, no handler/formatter/level set
  anywhere — `logger.error(...)` today falls back to Python's
  `logging.lastResort` (a bare `StreamHandler` to stderr, unformatted,
  timestamp-less). This is real but currently accepted debt, not silently
  glossed over: app-wide logging setup (handlers, format, level, interaction
  with uvicorn's own logger config) is a separate architectural decision,
  not something to bolt on as a side effect of one endpoint's error
  handling.

## `identity` HTTP interface — `GET /auth/me`
First protected read-style endpoint in `identity` (`register`/`login`/
`refresh`/`logout` are all public, token-issuing endpoints). Design decisions
made building it, several deliberately deviating from or extending existing
project patterns — noted here so they're not mistaken for oversights:

- **No dedicated use case class** — the router calls
  `OwnerRepository.get_by_id(account.owner_id)` directly (when `owner_id is
  not None`), matching the project's only precedent for a pure read (`GET
  /communities/{id}`, `GET /communities/{id}/quotas/{id}`: router →
  repository directly, no `GetX` use case). The project has zero read-only
  use case classes anywhere; do not introduce one for a future read endpoint
  without discussing it first.
- **Reuses the `Account` already returned by `get_current_account`
  (`dependencies.py:32-52`) — no second `AccountRepository.get_by_id()`
  call.** That dependency already re-reads the account from Postgres on
  every request; calling it again here would just be a redundant read, not
  extra safety.
- **`Owner` is embedded in full** (`AccountMeResponse.owner: OwnerResponse |
  None`), not just `owner_id` — because no `GET /owners/{id}` endpoint
  exists yet, so returning a bare id would give the frontend no way to ever
  fetch the linked Owner's `full_name`/NIF/phone. This is the **first
  cross-schema-module import** in the project (`auth_schemas.py` imports
  `OwnerResponse` from `owner_schemas.py`) — every other nested response
  schema until now composed sub-schemas defined in the same file, because
  every prior nesting was intra-aggregate (e.g. `CommunityResponse.units:
  list[UnitResponse]`); this is the first cross-aggregate read in the
  project.
- **`version` deliberately not exposed** — `/auth/me` is a pure read with no
  follow-up mutation on `Account` through this endpoint (unlike
  `QuotaResponse`, which does expose `version`, since `Quota` has no mutation
  either but the field was carried over from the aggregate anyway — mixed
  precedent noted, not a hard rule).
- **A dangling `account.owner_id` is handled as a bare `RuntimeError`, not a
  registered domain error with an HTTP mapping** — deliberately simpler than
  the analogous "theoretical" `CommunityNotFoundError`-from-inside-`vote` 500
  case (`## Business invariants` below). The two look similar but are NOT
  the same strength of guarantee: `Community` has no delete mechanism today
  (an absence, could change), while `accounts.owner_id` carries a real
  DB-level FK (`ON DELETE SET NULL`, `models.py:93-94`) — so a `owner_id`
  pointing at a nonexistent `Owner` is actively prevented by the schema, not
  just unobserved in practice. Same bare-`RuntimeError` pattern already used
  in `owners.py:47-50` for its own immediate-reread-after-write case. Not
  covered by any test — cannot be provoked without bypassing the FK.
- Tests (`tests/e2e/api/test_auth.py`) added the project's first assertion
  on the **body** of `get_current_account`'s 401
  (`{"detail": "Invalid or expired token"}`) and its first tampered/invalid-
  signature-token test case. Every prior `..._without_auth_header_returns_401`
  test in the project only asserted the status code, and only for the
  "header missing entirely" case — which is actually rejected upstream by
  `OAuth2PasswordBearer` before `get_current_account`'s own logic ever runs.

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
  `CommunityGroup`, `Quota`, and `Vote` all carry a `version: int` field.
  `Ballot` deliberately does NOT — it never mutates except the single
  supersede operation, and the real concurrency guard for `Ballot` is the DB
  partial-unique index below, not optimistic versioning. Repository `save()`
  does an upsert with `WHERE <table>.version = <expected_version>`, detects
  a skipped update via `RETURNING` (NOT `rowcount` — unreliable/`-1` with
  async psycopg on `ON CONFLICT ... WHERE`), and raises a per-aggregate
  `ConcurrentModificationError` (mapped to HTTP 412) if the version doesn't
  match. Any new mutable aggregate needs this same pattern (unless, like
  `Ballot`, it has its own dedicated concurrency mechanism instead).
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
- **`Vote.close()` never itself checks the deadline.** It only guards against
  double-close (`VoteAlreadyClosedError`). Whether `now > vote.end_date` is
  checked exclusively by the `CloseVote` use case (strictly `>`, not `>=` —
  cerrando exactamente en `end_date` podría rechazar un `Ballot` legítimo que
  llega en ese mismo instante). Symmetrically, `CastBallot` rejects any
  ballot where `now > vote.end_date` (`VoteHasEndedError`) even though
  `CloseVote` may not have run yet — a `Vote` whose deadline has passed but
  hasn't been closed is a normal, expected state (`CloseVote` is an explicit
  use case, never automatic), not an error state.
- **A `Vote` counts as "open" (blocking `Unit` coefficient/membership
  changes — see below) purely based on `result is None`, regardless of
  whether `end_date` has passed.** `VoteRepository.exists_open_vote_for_community`
  implements exactly this criterion — do not conflate it with an `end_date`
  comparison; the risk this guards against (coefficients changing between
  when ballots were cast and when `CloseVote` actually runs) persists for as
  long as `result` is `None`, independent of the deadline.
- **`Unit` coefficient/membership changes must be blocked while any `Vote` of
  that `Community` is open** (`result is None`). As of this writing, NO
  actual application use case exists that changes a `Unit`'s
  `participation_coefficient` or the community's set of units on an
  already-persisted `Community` — `AssignOwnerToUnit` is the only mutator of
  an existing `Community.units`, and it only changes `owner_ids`, never
  `participation_coefficient` or the unit count, so it is deliberately NOT
  blocked by this invariant and has a regression test proving it still
  works with an open vote. `VoteRepository.exists_open_vote_for_community(community_id)`
  is built and tested and ready to be wired in, but do NOT create a
  `CommunityHasOpenVoteError` or inject `VoteRepository` into any use case
  until an actual subdivision/coefficient-change use case is built — creating
  the error ahead of any caller was previously done once by mistake for
  `Vote.ConcurrentModificationError` and had to be reverted; don't repeat
  that pattern.
- **Two `IntegrityError`-backed race windows exist in `vote`, deliberately
  accepted (parallel to the `Quota` overlap-check exception above), with one
  now fully closed at the DB level**:
  - `CastBallot`'s "check active ballot, then decide create/supersede/reject"
    sequence has an inherent TOCTOU race between the read and the
    `Ballot.save()` — marked with a `# TODO(race-condition):` comment in
    `cast_ballot.py`. At the domain/repository level this is now CLOSED: the
    partial unique index below makes two concurrent "no active ballot" reads
    followed by two inserts result in exactly one success and one
    `ConcurrentBallotSubmissionError`. What remains open, deliberately, is
    that `CastBallot` itself does not yet catch/retry on
    `ConcurrentBallotSubmissionError` — that's future application-layer
    work, noted in the same comment.
  - `CreateQuota`'s ordinary-overlap check (see above) remains an accepted,
    unclosed race — different from `Ballot`'s, which now has a real DB
    constraint backing it.

## `Ballot` DB-level constraint — the partial unique index
`ballots` has `Index("ix_ballots_active_per_vote_unit", vote_id, unit_id,
unique=True, postgresql_where=(superseded_by_ballot_id IS NULL))` — the
FIRST partial index in this project (everything else is a plain
`UNIQUE`/index). It enforces "at most one active ballot per (vote_id,
unit_id)" while allowing unlimited historical (superseded) ballots for the
same pair. `PostgresBallotRepository.save()` catches the resulting
`IntegrityError`, inspects `error.orig.diag.constraint_name` (not the
message), and translates a hit on this specific index name to
`ConcurrentBallotSubmissionError` (domain error, `VoteDomainError` subclass);
any other `IntegrityError` is re-raised untranslated after the same
unconditional rollback used elsewhere.

**Real bug found and fixed during this work**: `superseded_by_ballot_id`'s
FK to `ballots.id` had to be declared `deferrable=True, initially="DEFERRED"`
(checked at `COMMIT`, not per-statement). `CastBallot`'s real save order is
`save(old_ballot)` (an UPDATE setting `superseded_by_ballot_id =
new_ballot.id`) THEN `save(new_ballot)` (an INSERT) — with an immediate FK,
the UPDATE fails because `new_ballot`'s row doesn't exist yet at that point.
Deferring the FK check to commit-time does NOT reopen the race the partial
index protects against: the old row stops counting as "active" for that
index the instant its `UPDATE` runs (its `superseded_by_ballot_id` is no
longer NULL), which happens before `new_ballot` is even inserted. Covered by
an integration test that failed before this fix and passes after
(`test_supersede_makes_new_ballot_active_and_keeps_old_one_persisted`).

## `Vote`/`Ballot` persistence shape
- `votes` table: `options` and `result` are stored as **JSONB** (first JSONB
  usage in the project), serialized/deserialized via pydantic
  `model_dump(mode="json")` / `model_validate` — chosen over relational child
  tables because both are effectively immutable-once-written blobs with no
  need for independent SQL querying (`options` fixed at creation, `result`
  written once atomically at `CloseVote`). `Decimal` fields inside
  (`weighted_coefficient`, `total_participation_coefficient`) survive the
  round trip with full precision because pydantic's `mode="json"` serializes
  `Decimal` as a string, not a float — verified explicitly with an 18-digit
  test case.
- **Real bug found and fixed**: the `result` JSONB column needed
  `JSONB(none_as_null=True)`. Without it, SQLAlchemy's default JSON/JSONB
  bind processor writes a Python `None` as the JSON literal `null` rather
  than SQL `NULL`, which silently broke `WHERE result IS NULL` (used by
  `exists_open_vote_for_community`) — the query returned zero rows for a
  genuinely open vote. Caught by an integration test against real Postgres,
  not by unit tests (a fake repository wouldn't hit this bind-processor
  behavior at all) — this is the concrete argument for why `vote`'s
  integration test suite exists and uses testcontainers+Alembic rather than
  trusting the fakes alone.
- `ballots` table is fully relational (not JSONB) since it's exactly what
  the partial unique index needs to enforce. `unit_id` and `option_id`
  columns carry NO foreign key (same reasoning as
  `QuotaAllocationModel.unit_id`): `Unit` rows are deleted and reinserted on
  every `Community.save()` (`PostgresCommunityRepository._replace_units`),
  so an FK with `ON DELETE CASCADE` would cascade-delete ballot history on
  unrelated community edits; `option_id` has no FK because `options` lives
  inside `VoteModel.options` (JSONB), not a relational table. Both are
  validated by the application layer (`CastBallot`/`CloseVote`), not the DB.

## Coding conventions
- Value Objects/Entities/Aggregates are immutable-by-default pydantic
  `BaseModel` (`frozen=True`); aggregate roots that mutate use
  `validate_assignment=True` instead of `frozen=True` (see pydantic exception
  below). Where an aggregate has some frozen fields and some mutable ones
  under `validate_assignment=True` (e.g. `Vote.options` vs `Vote.result`;
  every field of `Ballot` except `superseded_by_ballot_id`), the frozen
  fields use `Field(frozen=True)` individually — `validate_assignment=True`
  alone does NOT block reassignment of a field, it only re-runs validators
  on assignment; only `Field(frozen=True)` actually raises on reassignment.
  This was caught and fixed once already (`Vote.options`) — don't repeat the
  mistake of assuming "no setter method" is the same as "immutable".
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
  primitive-to-domain conversion left for the use case to do. `vote`'s use
  cases (`CreateVote`, `CastBallot`, `CloseVote`) all take an injected
  `now: datetime` parameter alongside the primitive IDs — never call
  `datetime.now()` internally, mirroring `Vote.create`/`Ballot.create`.
- Each application-layer use case in `vote` (`CreateVote`, `CastBallot`,
  `CloseVote`) defines its OWN local copies of shared-sounding errors
  (`AccountNotFoundError`, `CommunityNotFoundError`, etc.) rather than
  importing from one another — this mirrors the pre-existing convention in
  `create_quota.py`/`create_community_group.py` (each defines its own
  `CommunityNotFoundError` too). Do not "clean this up" into a shared module
  without discussing it first; it's consistent, deliberate duplication
  across the whole project, not an oversight local to `vote`.
- Everything — domain concepts, aggregates, events, use cases, comments,
  variable names — is in English. Exceptions: `CIF` and `NIF`/`NIE` (Spanish
  legal identifiers with no English equivalent) keep their original names.
- Cross-aggregate existence checks (e.g. "does this Owner exist before linking
  it") belong in the application-layer use case, never inside the aggregate
  itself — an aggregate can only validate itself, not query other aggregates'
  repositories. Same rule applied throughout `vote`: `Ballot` cannot validate
  that its `option_id` belongs to the `Vote`'s options, or that `unit_id`
  belongs to the right `Community` — those checks live in `CastBallot`.
- Every FastAPI route MUST set `summary`, an English `description` (behavior
  and business invariants the API consumer needs to know, not a restatement
  of the code), an explicit `response_model`, and `responses={...}` documenting
  each domain-error HTTP status the endpoint can actually return (400, 404,
  409, 412, 422, 500) with a short English description of when it occurs.
  This is the sole source of API documentation — FastAPI's generated OpenAPI
  schema (`/docs`, `/openapi.json`), no hand-written docs files. `vote`'s
  routers (`POST /communities/{community_id}/votes`, `POST
  /votes/{vote_id}/ballots`, `POST /votes/{vote_id}/close`) are now built —
  see the "`vote` HTTP interface" section below for the error-mapping
  conventions established while building them, which apply to any future
  router in the project, not just `vote`.

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
  (missing constraints, wrong precision). To run this locally you need a real
  Postgres reachable at `DATABASE_URL` — use `docker compose up -d db` (see
  "Local dev DB" above), export
  `DATABASE_URL=postgresql+psycopg://vecinio:vecinio@localhost:5433/vecinio`, # pragma: allowlist secret
  run `alembic upgrade head` first, then autogenerate, then `docker compose
  down` when finished. For a `postgresql_where` partial index, ALSO verify
  the generated DDL directly against a live Postgres (`\d <table>` in `psql`)
  — autogenerate can silently produce a full index instead of a partial one
  if the model declaration is wrong; don't trust the migration file's
  Python source alone for this case.
- Apply migrations: `uv run alembic upgrade head`
- Pre-commit (all hooks, forced): `uv run pre-commit run --all-files`
- **Note**: `.pre-commit-config.yaml` has `exclude: ^migrations/` — this means
  NO hook (black, isort, flake8, mypy, pydocstyle, complexipy, detect-secrets)
  has ever actually checked any file under `migrations/versions/`, for any
  migration, ever. This is a known, accepted gap, not yet revisited.
- Run local frontend dev server: `cd frontend && npm run dev` (serves on
  `http://localhost:5173` by default; requires the backend running too, see
  "Run local API" above, plus `docker compose up -d db`).

## Frontend
`frontend/` was an empty placeholder until the first slice (auth +
register-a-Community-with-its-Units) was built. Stack, decided at that
point:
- **Build tool**: Vite, scaffolded via `npm create vue@latest` (the official
  `create-vue` scaffolder — chosen over Vuetify's own `create-vuetify`
  wizard because its generated layout is more predictable/reviewable).
  JavaScript, NOT TypeScript, for now — deliberate: the person building this
  is new to the Composition API, to Vuetify's component API, and to
  component-library-driven UI (no prior UX/UI design background) all at
  once; adding TS as a fourth simultaneous unknown was judged likely to
  cause tooling friction rather than product-logic friction. Revisit once
  the Composition API feels comfortable — migrating a Vite project to TS
  later is cheap.
- **UI library**: Vuetify (Material Design components) + `@mdi/font` for
  icons, wired via `vite-plugin-vuetify`. Chosen deliberately over
  PrimeVue/Tailwind: Vuetify's opinionated Material Design defaults
  (layout, spacing, color roles) remove most of the visual-design decisions
  a UX-inexperienced developer would otherwise have to make from scratch.
- **State**: Pinia (per the Tech stack entry above). **Routing**:
  `vue-router`, scaffolded by `create-vue`.
- **HTTP client**: `axios`, wrapped in a single `src/api/client.js` instance
  — request interceptor attaches `Authorization: Bearer <token>` from the
  Pinia auth store (skipped for the public `/auth/*` calls); response
  interceptor logs out and redirects to `/login` on any `401`. No
  automatic refresh-and-retry-on-401 loop exists yet — deliberately
  deferred (needs a request queue to avoid parallel refresh calls; the
  15-minute access token TTL made this non-essential for the first slice).
- **Auth token storage**: plain `localStorage`, written through from Pinia
  store actions (not httpOnly cookies — the backend returns tokens as JSON
  fields, not `Set-Cookie`, and adopting cookies would need backend changes
  — CSRF handling, `SameSite`/`Secure` flags — not done; not memory-only
  Pinia state either, since that would log the user out on every page
  refresh). Accepted trade-off: `localStorage` is readable by any JS
  running on the page, so an XSS hole would expose both the access token
  and the 30-day refresh token. Fine for a pre-production app with no real
  HOA member data yet — revisit before that stops being true.
- **`GET /auth/me` now exists** — returns the current `Account`'s `id`/
  `email` plus its linked `Owner` embedded in full (`nif`/`full_name`/
  `email`/`phone`), or `owner: null` if none is linked. See the
  "`identity` HTTP interface" section below for the design decisions behind
  its shape. The frontend does not call it from anywhere yet — wiring it
  into the Pinia auth store (e.g. on app boot, replacing client-side JWT
  decoding for "who am I") is still pending.
- **No community/owner/vote list endpoints exist yet** — only
  `GET /communities/{id}` and `GET /communities/{id}/quotas/{id}` (by id).
  There is no "browse all my communities" screen possible yet; a created
  Community is only reachable by navigating straight to its detail route
  right after creation.
- **Units can only be created inline as part of `POST /communities`** — no
  standalone "add a unit to an existing community" endpoint exists (see
  "Bounded contexts implemented so far" above). This is why the first
  frontend flow is a single combined community+units form, not two
  separate ones — it mirrors what the backend actually supports, not an
  arbitrary UI simplification.
- CORS is now configured in `src/interfaces/api/main.py`
  (`CORSMiddleware`), but the allowed-origins list is hardcoded to Vite's
  local dev ports (`localhost:5173`/`127.0.0.1:5173`) — must become
  environment-driven before any real deployment.

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
- Do not add `asyncpg` — the project standardized on `psycopg` (async) as the
  single Postgres driver.
- Do not use `passlib` for anything — unmaintained, already replaced by
  `pwdlib`.
- Do not create `CommunityHasOpenVoteError` or wire `VoteRepository` into any
  `community` use case until an actual subdivision/coefficient-change use
  case exists (see the `Unit`-lock invariant above) — there is nowhere
  legitimate to call it from yet.
- Do not make `CastBallot` catch/retry on `ConcurrentBallotSubmissionError`
  without discussing the retry strategy first — the error exists and is
  correctly raised by the repository, but the application-layer handling of
  it (retry once? surface a 409? something else?) hasn't been decided.

# Session-digest file
Read the file .claude/session_digest.md to have more context of the current project.
