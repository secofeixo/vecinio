# ADR-0011: `Quota` ordinary-overlap check — accepted race window; project-wide concurrency-retry strategy is open

## Status
Accepted (the race window). Open (the general retry strategy).

## Decision: Quota overlap
An ordinary `Quota`'s period must not overlap another ordinary `Quota` of the
SAME `Community` (inclusive on both bounds). Checked in `CreateQuota` via
`QuotaRepository.exists_overlapping_ordinary` (an aggregate can only validate
itself, not query other persisted rows), raising `OverlappingOrdinaryQuotaError`
(HTTP 400). `extraordinary` quotas are never checked against anything.

**Deliberate exception to the project's DB-guaranteed-uniqueness pattern**
(`Unit.identifier`, `CommunityGroup.slug`): backed only by a plain
(non-unique) index on `(community_id, type, period_start, period_end)` for
query efficiency, NOT a DB-level uniqueness/exclusion constraint. Two
concurrent `POST`s creating overlapping ordinary quotas can both succeed —
accepted given expected write volume (ordinary-quota creation is at most
annual per community). If write volume ever grows enough to matter, the
correct fix is a Postgres `EXCLUDE` constraint using `btree_gist`, not
tightening the use-case check alone.

## Open question: concurrency-collision retry strategy
`ConcurrentBallotSubmissionError`/`ConcurrentModificationError` (409/412)
have no automatic retry anywhere in the project. This is an OPEN,
project-wide design question, not closed locally to any one endpoint:
whether/how a router should retry once, surface a plain error, or something
else, on a concurrency collision hasn't been decided and shouldn't be solved
ad hoc for a single endpoint. `POST /votes/{vote_id}/close`'s
`responses={412: ...}` docstring says this explicitly — mirror that wording
if this comes up elsewhere before the general strategy is designed.

See also ADR-0006 (Ballot's DB-backed race is closed at the constraint level,
only the retry-on-error layer is open).

## Do not
- Do not add a DB-level exclusion constraint for Quota overlap without
  discussing it first (current index is deliberately non-unique).
- Do not implement retry-on-409/412 for any single endpoint without first
  deciding the project-wide strategy.
