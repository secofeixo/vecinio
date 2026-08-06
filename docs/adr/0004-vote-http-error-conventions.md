# ADR-0004: `vote` HTTP interface — error-mapping and non-enumeration conventions

## Status
Accepted, implemented. Precedent for future routers, not local to `vote`.

## Endpoints
`POST /communities/{community_id}/votes` (CreateVote), `POST
/votes/{vote_id}/ballots` (CastBallot), `POST /votes/{vote_id}/close`
(CloseVote). `CastBallot`/`CloseVote` deliberately do NOT nest under
`/communities/{community_id}/...` — neither use case takes a `community_id`
(derived internally from `vote.community_id`); nesting would require a new
"does this vote belong to this community" validation that doesn't exist and
shouldn't be added just for URL aesthetics.

## Decision: non-enumeration via unified 404/409 bodies
Generalizes the existing login (`InvalidCredentialsError`) pattern: any check
of the shape "does X exist AND do you have access to it" returns an
**identical response body**, not just the same status code — a differentiated
message turns the endpoint into an enumeration oracle for whichever
identifier is sensitive.

- `CreateVote`: `CommunityNotFoundError` and
  `AccountNotAuthorizedToCreateVoteError` → 404, `{"detail": "Community not
  found or you are not a member of it"}`.
- `CastBallot`: `AccountNotAuthorizedToCastBallotError` covers two distinct
  causes (no linked owner; owner doesn't own the unit) → one 404, `{"detail":
  "Not authorized to cast a ballot for this unit"}`.
- `CloseVote`: same pattern, `{"detail": "Not authorized to close this
  vote"}`.

**Deliberate exception, NOT unified**: `UnitNotFoundInCommunityError` in
`CastBallot` stays differentiated from the authorization 404 — a caller CAN
tell "unit doesn't exist" apart from "unit exists but isn't yours". Accepted
because `unit_id` never appears in a URL in this context (only request
bodies), unlike `community_id`, which is exposed in
`POST /communities/{community_id}/votes`'s path and could leak through shared
links between neighbors. This exposure asymmetry — not a general claim that
`unit_id` is less sensitive — is the actual reason. Revisit if `unit_id`
starts appearing in a URL anywhere.

**Rule**: any handler backing a unified message must use a fixed string,
ignoring `str(exc)`. Confirmed necessary the hard way: the same exception
type raised from inside an aggregate method (interpolating a pydantic Value
Object) renders differently from the same exception raised from an
application-layer use case (interpolating a raw `UUID`) — `Vote.close()` vs.
`CloseVote.execute()` produced different strings for the literal same error.
Never wire a precedence-sensitive test's assertion to `str(exc)` without
first printing both call sites' actual output side by side.

## Decision: `LinkOwnerToAccount` unifies a body-only identifier anyway
The `vote` convention above unifies messages specifically when an identifier
is exposed in a URL. `POST /auth/me/link-owner` unifies a NIF anyway (see
ADR-0009) — a NIF's sensitivity comes from being a real government ID tied to
a human, not from where it appears in the request. The underlying principle
(don't let a caller learn a sensitive identifier's existence) generalizes
beyond the URL-vs-body letter of this ADR.

## Consequences
Any future router documenting 400/404/409/412/422/500 responses should
follow this unify-vs-differentiate reasoning, not copy a status code blindly.
