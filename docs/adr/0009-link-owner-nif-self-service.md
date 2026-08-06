# ADR-0009: `POST /auth/me/link-owner` — NIF-only self-service, no identity verification

## Status
Accepted, implemented. **Do not silently harden without discussion** (see
`CLAUDE.md` "Do NOT do without asking").

## Decision
Self-service linking for an already-registered `Account` to an existing
`Owner`. Caller supplies a NIF/NIE; if an unclaimed `Owner` with that NIF
exists, the `Account` is linked immediately. No email confirmation, no
invitation token, nothing checking the caller is actually that person.

## Rationale
Deliberately accepted trade-off, not an oversight: a NIF is a real,
non-secret government identifier (visible on deeds, mailboxes, community
boards), so this is a land-grab — whoever enters a given NIF first claims
that `Owner` identity.

Considered and explicitly rejected: bundling owner-creation into this flow
(would double the endpoint's scope and reintroduce the "is self-registering
a legal identity safe without verification" question for the create path
too — `POST /owners` remains the only way to create an `Owner`).

A partial fix (checking `Owner.email == Account.email`) was considered and
rejected — the two emails are independently set today and aren't guaranteed
to match for a legitimate owner.

## Enumeration protection
"NIF not found" and "NIF found but already linked to someone else" return a
byte-identical 409 body — deliberately stricter than the `vote` HTTP
convention (ADR-0004), which unifies only when an identifier is exposed in a
URL. This endpoint unifies a body-only identifier anyway because a NIF's
sensitivity comes from being tied to a specific human, not from its
placement in the request.

The same shared handler also covers the domain-level
`OwnerAlreadyLinkedError` raised by `PostgresAccountRepository.save()` on
the DB-race path (two concurrent link requests for the same still-unclaimed
NIF) — indistinguishable from the ordinary already-linked case to the
caller, so gets the same response.

`RegisterAccount` has its own, deliberately NOT unified, `OwnerAlreadyLinkedError`
check for the `owner_id` supplied at registration — that's an opaque UUID in
the request body, not a NIF, same reasoning `vote` used to treat `unit_id`
as lower-sensitivity than `community_id`.

## Real gap found and closed
`accounts.owner_id` had no uniqueness enforcement anywhere (DB or app level)
since `identity` was first built. Closed with a genuine DB-level `UNIQUE`
constraint (`uq_accounts_owner_id`) — treated as security-relevant (prevents
account-hijack race), same class of decision as ADR-0006's partial index.

## Revisit trigger
Once a `governance`/invitation-based flow exists (see `session_digest.md`).
