# ADR-0001: Auth stack — JWT + opaque refresh, pwdlib/argon2id

## Status
Accepted, implemented.

## Decision
- JWT access tokens (~15 min TTL) + opaque refresh tokens (long-lived, hashed
  at rest, revocable).
- Password hashing via `pwdlib` + argon2id.

## Rationale
- **Not `passlib`**: unmaintained, compatibility warnings with modern bcrypt.
- **Not bcrypt directly**: silent 72-byte truncation footgun that argon2id
  doesn't have.
- Opaque (not JWT) refresh tokens so they can be revoked server-side; access
  tokens stay short-lived and stateless for cheap verification.

## Consequences
- No automatic refresh-and-retry-on-401 loop exists yet on the frontend
  (deferred — see ADR-0012). The 15-minute access token TTL made this
  non-essential for the first slice.
- Do not reintroduce `passlib` or raw `bcrypt` without reopening this ADR.
