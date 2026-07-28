# CLAUDE.md — Homeowners Association Management

## Purpose of this file
This file is loaded automatically in every Claude Code session. It contains ONLY what
Claude Code would otherwise need to discover by reading code or asking — not product
documentation.

## Tech stack
- **Backend**: Python 3.12+, FastAPI
- **Persistence**: PostgreSQL (relational + JSONB where it fits)
- **Architecture**: Tactical DDD (no CQRS, no Event Sourcing)
- **Traceability**: Domain Events persisted in `audit_log` + Outbox pattern for future integrations
- **Frontend**: Vue 3 (Composition API) + Pinia — later phase, do not touch yet
- **Testing**: pytest (unit), testcontainers (integration against real Postgres), Playwright or httpx (e2e)

## Architecture: layers and dependencies
```
domain/        → Entities, Value Objects, Aggregates, Domain Events, repository interfaces.
                 ZERO external dependencies (no FastAPI, no SQLAlchemy, no infra of any kind).
application/   → Use cases (command/query handlers). Orchestrates the domain. No business rules here.
infrastructure/→ Repository implementations (SQLAlchemy/Postgres), outbox, external adapters.
interfaces/    → FastAPI routers, Pydantic input/output schemas, DTO ↔ domain mapping.
```
Dependency rule: `interfaces` → `application` → `domain` ← `infrastructure`.
The domain layer NEVER imports from `infrastructure` or `interfaces`.

## Business invariants already decided (do not reopen without explicit confirmation)
- `Owner` is an independent aggregate (own identity, can belong to 0..N communities).
- `Unit` is an entity INSIDE the `Community` aggregate (not its own aggregate), because the invariant
  "sum of participation coefficients of all units = 100%" requires transactional consistency.
- `Unit.owner_ids` is a list (co-ownership supported). JOINT AND SEVERAL liability:
  each co-owner is liable for 100% of that unit's dues; liability is NOT split proportionally.
- Invariant validation lives in aggregate methods, NEVER in the FastAPI router or the use case.
  Every entry point into the system (API, batch import, scheduled job) must go through the aggregate.

## Coding conventions
- Value Objects are immutable (`@dataclass(frozen=True)` or `pydantic.BaseModel` with `frozen=True`).
- Repositories are defined as interfaces (Protocol/ABC) in `domain/`, implemented in `infrastructure/`.
- One use case = one class with a single `execute()` method. Do not merge two use cases into one handler.
- Domain IDs are typed Value Objects (`CommunityId`, `OwnerId`), never a bare `str` or `UUID`
  crossing layers.
- Everything — domain concepts, aggregates, events, use cases, comments, variable names — is in
  English. Exceptions: `CIF` and `NIF` (Spanish legal identifiers with no English equivalent) keep
  their original names as domain-specific Value Objects.

## Commands
- Install dependencies: `poetry install` (or `pip install -r requirements.txt`, decide package manager before the first task)
- Unit tests: `pytest tests/unit`
- Integration tests: `pytest tests/integration` (requires Docker running, uses testcontainers)
- E2E tests: `pytest tests/e2e`
- Run local API: `uvicorn src.interfaces.api.main:app --reload`

## Domain purity exception: pydantic
`domain/` uses `pydantic.BaseModel` (with `frozen=True`) for Entities and Value Objects.
This is a deliberate, accepted exception to "pure Python domain" — decided for the
concrete benefits below, not as a general license to add dependencies to `domain/`:
- Declarative validation at construction time (invariants enforced without hand-written
  `__post_init__` boilerplate).
- Immutability and hashability out of the box (needed for VO equality and for using
  IDs in sets/dicts, e.g. duplicate-unit-id checks).
- Free JSON (de)serialization when domain objects cross into `interfaces/` — though
  domain objects should still not be returned directly from API responses; map to schemas.

Trade-off accepted knowingly: pydantic controls the validation lifecycle
(`model_validator`, `validate_assignment`) instead of the developer deciding explicitly
when each rule fires. This is less control, not more flexibility — do not cite
"flexibility" as the reason if this decision is revisited later.

This exception applies ONLY to pydantic. It does not extend to ORMs, HTTP clients, or
any other infrastructure-flavored library. Any other proposed dependency in `domain/`
requires the same explicit trade-off discussion as this one — it is not pre-approved
by this precedent.

## Do NOT do without asking
- Do not introduce CQRS, Event Sourcing, or a second database.
- Do not add dependencies to `domain/` beyond pydantic (see exception above) without
  discussing the specific trade-off first.
- Do not touch `frontend/` yet — out of scope until the backend has stable use cases.