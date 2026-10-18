# Architecture and data

Read this when a change crosses a module boundary, an API contract, or stored
data. It decides two things: whether the existing structure stays, and what has
to be true before a change to a contract or a schema is safe.

Preserve the existing architecture unless the requested outcome requires a
change. Read only the sections the task touches.

## Structure

- Prefer an existing module boundary over introducing a service. Distribution
  needs a concrete requirement and adds failure, versioning, deployment, and
  observation costs.
- Do not add an interface, factory, repository, event bus, or generic
  abstraction without a demonstrated consumer or variation. SOLID and design
  patterns explain a concrete choice; they are not work to add.
- Track backward compatibility at the boundary. An internal refactor is not
  automatically invisible to callers.

## Algorithms and resources

- Verify constant factors with a representative measurement before claiming a
  complexity win.
- Specify numeric range, precision, overflow, Unicode, locale, and time-zone
  semantics when they affect correctness.
- Asynchronous execution does not make an operation thread-safe. Identify
  shared state, ordering, atomicity, cancellation, and disposal.
- Bound queues and work; handle backpressure where the workload requires it.

## API contracts

- Distinguish an absent value from an explicit empty or null value.
- Define idempotency and duplicate handling before adding a retry to a
  side-effecting request.
- A successful status does not mean the intended side effect completed.
- Exercise actual boundary behavior in a contract test, not a mock's shape.
- Document deprecation and migration only when a public contract changes.

## Data and persistence

- Choose transaction scope and isolation from the invariant being protected,
  and account for concurrent updates, lost writes, and consistency after
  failure.
- Parameterize queries and authorize object access on the trusted side.
- Avoid an N+1 query, an unbounded read, and an accidental full-table update in
  the changed path. Justify an index with a query plan and representative data,
  not with a guess.
- A cache needs ownership, keys, expiry or invalidation, and stale-data
  semantics.
- A schema change requires explicit authorization under the user's environment
  policy. When authorized, plan compatibility, backfill, locking, rollback
  limits, and verification. A rollback does not necessarily restore lost data.
  Never run a migration to unblock an unrelated test.

## Distributed behavior

- Do not promise an exactly-once business effect because a queue advertises a
  delivery mode. Define deadlines, retry budgets, deduplication, ordering, and
  partial-failure recovery against the actual requirement.
- Distinguish availability from correctness. Assess clock assumptions,
  replication lag, and partition behavior for the affected workload.
- State an unresolved tradeoff rather than settling it with an infrastructure
  choice.

For implementation, return to the [technology guide](KNOWLEDGE_MAP.md) and the
[Coding workflow](../Coding/WORKFLOW.md).
