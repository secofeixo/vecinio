# ADR-0003: Tactical DDD, explicitly rejecting CQRS and Event Sourcing

## Status
Accepted.

## Decision
The project uses tactical DDD (aggregates, entities, value objects,
repositories, use cases) without CQRS and without Event Sourcing.

## Rationale
Not documented in detail beyond "deliberately rejected" — the project's scale
and team size (single developer, early-stage product) do not justify the
operational complexity of separate read/write models or an event store.
`audit_log.py` and `outbox_repository.py` exist as empty stub files — a
domain-events + outbox pattern was the plan for a possible future
audit/integration need, but nothing has been built against them.

## Consequences
- Do not introduce CQRS, Event Sourcing, or a second database without
  reopening this ADR.
- Do not assume `audit_log.py` / `outbox_repository.py` do anything — they
  are stubs.
