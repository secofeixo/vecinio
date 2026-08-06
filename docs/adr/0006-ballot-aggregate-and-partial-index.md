# ADR-0006: `Ballot` as its own aggregate, backed by a DB partial unique index

## Status
Accepted, implemented.

## Decision
`Ballot` is its own aggregate (not an entity inside `Vote`) — needed a
DB-level `UNIQUE` constraint for concurrency safety, incompatible with living
inside `Vote`'s transactional boundary.

Fields: `id, vote_id, unit_id, option_id, cast_by_owner_id, cast_at` all
`Field(frozen=True)`; `superseded_by_ballot_id: BallotId | None = None` is
the only mutable field. `supersede(by)` checks `by == self.id`
(`BallotCannotSupersedeItselfError`, checked first — more fundamental,
independent of current state) then
`self.superseded_by_ballot_id is not None`
(`BallotAlreadySupersededError`).

**Product decision**: a unit's ballot can only be corrected (superseded) by
the SAME owner who originally cast it — a different co-owner of the same
`Unit` cannot override it. Enforced by `CastBallot` (cross-aggregate
concern), not the aggregate itself.

`Ballot` deliberately does NOT carry `version` (unlike every other mutable
aggregate) — it never mutates except the single supersede operation; the
real concurrency guard is the DB partial-unique index, not optimistic
versioning.

## DB constraint
`ballots` has `Index("ix_ballots_active_per_vote_unit", vote_id, unit_id,
unique=True, postgresql_where=(superseded_by_ballot_id IS NULL))` — the
FIRST partial index in this project. Enforces "at most one active ballot per
(vote_id, unit_id)" while allowing unlimited historical (superseded)
ballots. `PostgresBallotRepository.save()` catches the resulting
`IntegrityError`, inspects `error.orig.diag.constraint_name` (not the
message), translates a hit on this index name to
`ConcurrentBallotSubmissionError`; any other `IntegrityError` is re-raised
untranslated after the same unconditional rollback used elsewhere.

`unit_id` and `option_id` columns carry NO foreign key: `Unit` rows are
deleted and reinserted on every `Community.save()`
(`PostgresCommunityRepository._replace_units`), so an FK with
`ON DELETE CASCADE` would cascade-delete ballot history on unrelated
community edits; `option_id` has no FK because `options` lives inside
`VoteModel.options` (JSONB, see ADR-0007), not a relational table. Both
validated at the application layer (`CastBallot`/`CloseVote`), not the DB.

## Bug found and fixed: deferred FK
`superseded_by_ballot_id`'s FK to `ballots.id` had to be declared
`deferrable=True, initially="DEFERRED"` (checked at COMMIT, not
per-statement). `CastBallot`'s real save order is `save(old_ballot)` (UPDATE
setting `superseded_by_ballot_id = new_ballot.id`) THEN `save(new_ballot)`
(INSERT) — with an immediate FK, the UPDATE fails because `new_ballot`'s row
doesn't exist yet. Deferring to commit-time does NOT reopen the race the
partial index protects: the old row stops counting as "active" the instant
its UPDATE runs (superseded_by_ballot_id no longer NULL), before
`new_ballot` is even inserted. Covered by
`test_supersede_makes_new_ballot_active_and_keeps_old_one_persisted`
(failed before, passes after).

## Open, deliberately unresolved
`CastBallot`'s "check active ballot, then decide create/supersede/reject"
sequence has an inherent TOCTOU race between the read and `Ballot.save()`
(`# TODO(race-condition):` in `cast_ballot.py`). At the domain/repository
level this is CLOSED by the index above. What remains open: `CastBallot`
does not catch/retry on `ConcurrentBallotSubmissionError` — future
application-layer work, not to be added without discussing the
project-wide concurrency-retry strategy first (see also ADR-0011).
