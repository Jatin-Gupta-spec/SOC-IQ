# ADR-005: SQLite Remains the Database

**Status:** Proposed
**Related:** Master Plan §28, §17.

## Context

The current application uses SQLite (`app/database/*`) with parameterized queries throughout
(CONFIRMED). The target architecture introduces a multi-process boundary (Python sidecar +
Tauri + React), raising the question of whether a client-server database (e.g. Postgres)
becomes necessary.

## Problem

Multi-process architectures sometimes default to a client-server database "for safety," even
when the actual concurrency profile doesn't require it.

## Decision

SQLite is retained. SOC-IQ is a single-user desktop application; only one process (the Python
sidecar) ever writes to the database, and the frontend never accesses it directly (ADR-001,
ADR-002). There is no concurrent-multi-writer requirement that Postgres would solve.

## Alternatives Considered

- **Postgres**, run as a bundled or system service. Rejected — adds a second database
  process to package, run, and secure, for a concurrency profile SQLite already handles; no
  concrete requirement identified in the checkpoint or target architecture justifies it
  (Master Plan §17: "Do not introduce Postgres unless there is a concrete requirement").

## Rejected Alternatives (explicit)

An embedded document store (e.g. a JSON-file-per-investigation approach) — rejected; would
lose the relational integrity, indexing, and query capability the existing repository pattern
already provides and that the correlation feature (Master Plan §5.3, §13) depends on.

## Consequences

- Positive: no new database technology to learn, package, or secure; the existing
  parameterized-query repository pattern is preserved unchanged (see
  `docs/architecture/09-database-architecture.md`).
- Negative: SQLite's single-writer model means the Python sidecar must serialize its own
  writes carefully if any future feature introduces internal concurrency — tracked as a
  design constraint, not a current problem.

## Security Implications

Keeping the database as a single, non-networked file reduces the security surface — there is
no database network port to secure or expose, unlike a client-server database would require.

## Migration Implications

A migration runner is introduced (see `docs/architecture/09-database-architecture.md`)
specifically because SQLite is being kept long-term and needs a versioning strategy it
currently lacks — this ADR is the reason that work is scoped as "add migrations to SQLite,"
not "migrate off SQLite."
