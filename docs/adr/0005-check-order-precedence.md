# ADR-0005: Check-order precedence is a tested contract

## Status
Accepted, implemented. Applies project-wide, established while building `vote`.

## Decision
Every use case's internal `if`/`raise` sequence determines which error a
request with multiple simultaneous problems gets. This ordering must be
pinned down explicitly with its own e2e test per non-obvious ordering — not
left for whoever refactors the use case later to notice or not.

## Confirmed orderings (see `tests/e2e/api/test_votes.py`)
- **`CreateVote`**: account exists → account has linked owner → community
  exists → owns a unit in it → *then* `Vote.create()` runs. A malformed vote
  payload against a nonexistent/foreign community still returns 404, never
  400 — membership check wins.
- **`CastBallot`**: vote exists → vote hasn't ended → account exists →
  account has linked owner → option belongs to vote → community exists
  (theoretical) → unit exists in community → owner owns this unit.
  Counter-intuitive rows: an ended vote wins over a garbage
  `unit_id`/`option_id` (409, not 404); option-membership check is checked
  BEFORE "do you own this unit", even though both map to the same unified
  404 body.
- **`CloseVote`**: `vote.result is not None` (→ `VoteAlreadyClosedError`) is
  checked in `CloseVote.execute()` BEFORE the `end_date` check (→
  `VoteHasNotEndedYetError`) — reordered deliberately. `Vote.close()` still
  also guards the same thing internally (deliberate duplication: the
  aggregate protects itself regardless of caller; the use case additionally
  short-circuits for correct HTTP-boundary precedence). Before this change,
  a (today-unreachable-via-HTTP, only-via-repository-bypass) already-closed
  vote whose `end_date` hadn't arrived would have wrongly returned "has not
  ended yet" instead of "already closed".

## Consequences
Any new use case with more than one failure mode needs its own ordering
decision recorded and tested, not left implicit in code review.
