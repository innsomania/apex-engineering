# Architecture and data

Use the sections touched by the task. Preserve the existing architecture unless the requested outcome requires a change.

## Boundaries and domain rules

Identify invariants, ownership, dependency direction, and lifecycle. Keep domain decisions separate from transport and persistence when this makes the actual change easier to reason about. Prefer an existing module boundary over introducing a service. Distribution requires a concrete need and brings failure, versioning, deployment, and observation costs.

Use SOLID, cohesion, coupling, dependency inversion, and domain modeling to explain a concrete design choice. Do not add interfaces, factories, repositories, event buses, or generic abstractions without a demonstrated consumer or variation. Track backward compatibility at the boundary rather than assuming an internal refactor is invisible.

## Algorithms and resource behavior

Choose data structures based on access patterns, cardinality, ordering, mutation, and memory limits. Analyze time and space complexity where input growth matters; verify constant factors with representative measurements. Specify numeric ranges, precision, overflow behavior, Unicode, locale, and time-zone semantics when they affect correctness.

For concurrency, identify shared state, ownership, ordering, atomicity, cancellation, and resource disposal. Do not assume asynchronous execution makes an operation thread-safe. Bound queues and work; handle backpressure and starvation where the workload requires it.

## API and integration contracts

Specify input validation, output shape, error semantics, authorization, pagination, timeouts, and compatibility. Distinguish an absent value from an explicit empty/null value. Define idempotency and duplicate handling before adding retries to side-effecting requests. Preserve correlation information without exposing secrets.

Consider API consumers, event consumers, SDKs, and old clients during evolution. Document deprecation and migration only when changing a public contract. Contract tests should exercise actual boundary behavior. Never assume a successful status means the intended side effect completed.

## Data ownership and persistence

Identify authoritative records, keys, uniqueness, relationships, retention, and tenant boundaries. Choose transaction scope and isolation from the invariant being protected. Consider concurrent updates, lost writes, consistency after failure, and audit requirements. Parameterize queries and authorize object access on the trusted side.

Use query plans and representative data to justify indexes or performance work. Evaluate write cost and storage impact. Avoid N+1 queries, unbounded reads, and accidental full-table updates in the changed path. Caches need ownership, keys, expiry/invalidation, and stale-data semantics.

Schema changes require explicit authorization under the user's environment policy. When authorized, plan compatibility, backfill, locking, rollback limits, and verification. A migration rollback does not necessarily restore lost data. Do not run migrations merely to unblock unrelated tests.

## Distributed behavior

Specify what can fail independently and what callers observe. Define deadlines, retry budgets, deduplication, delivery semantics, ordering, and partial-failure recovery. Do not promise exactly-once business effects solely because a queue advertises a delivery mode. For multi-step updates, consider transactional outbox or compensation only when the actual consistency requirement warrants it.

Use health/readiness signals that reflect the service contract. Distinguish availability from correctness. Assess clock assumptions, replication lag, partition behavior, and disaster recovery for the affected workload. Document unresolved tradeoffs rather than hiding them behind infrastructure choices.

For implementation, return to the appropriate [technology guide](KNOWLEDGE_MAP.md) and [Coding workflow](../Coding/WORKFLOW.md).
