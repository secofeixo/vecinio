# ADR-0008: `GET /auth/me` design decisions

## Status
Accepted, implemented.

## Context
First protected read-style endpoint in `identity` (`register`/`login`/
`refresh`/`logout` are all public, token-issuing endpoints).

## Decisions
- **No dedicated use case class** — router calls
  `OwnerRepository.get_by_id(account.owner_id)` directly, matching the
  project's only precedent for a pure read (`GET /communities/{id}`,
  `GET /communities/{id}/quotas/{id}`). The project has zero read-only use
  case classes anywhere; do not introduce one for a future read endpoint
  without discussing it first.
- **Reuses the `Account` already returned by `get_current_account`** — no
  second `AccountRepository.get_by_id()` call. That dependency already
  re-reads the account from Postgres on every request.
- **`Owner` embedded in full** (`AccountMeResponse.owner: OwnerResponse |
  None`), not just `owner_id` — no `GET /owners/{id}` endpoint exists yet,
  so a bare id would give the frontend no way to fetch the linked Owner's
  data. First cross-schema-module import in the project
  (`auth_schemas.py` imports `OwnerResponse` from `owner_schemas.py`) and
  first cross-aggregate read.
- **`version` deliberately not exposed** — pure read, no follow-up mutation
  on `Account` through this endpoint (mixed precedent: `QuotaResponse` does
  expose `version` despite `Quota` also having no mutation — carried over
  from the aggregate, not a hard rule).
- **A dangling `account.owner_id` is a bare `RuntimeError`**, not a
  registered domain error with an HTTP mapping — deliberately simpler than
  the `CommunityNotFoundError`-from-inside-`vote` 500 case: `Community` has
  no delete mechanism today (an absence, could change), while
  `accounts.owner_id` carries a real DB-level FK
  (`ON DELETE SET NULL`, `models.py:93-94`), so this state is actively
  prevented by the schema. Not covered by any test — cannot be provoked
  without bypassing the FK.

## Consequences
`tests/e2e/api/test_auth.py` added the project's first assertion on the
**body** of `get_current_account`'s 401
(`{"detail": "Invalid or expired token"}`) and its first
tampered/invalid-signature-token test.
