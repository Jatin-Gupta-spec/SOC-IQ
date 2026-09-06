# Database Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §17, §1.7 (current-state facts), ADR-005.

## CURRENT STATE

`app/database/repository.py` (613 LOC) uses parameterized SQL throughout (CONFIRMED, no
string-interpolated queries observed in prior audit and spot-check). No schema-version or
migration table was observed in `connection.py`/`models.py` during this pass — this is
**LIKELY** true (no migration strategy exists) but is not exhaustively confirmed and is
flagged below.

## TARGET STATE (PROPOSED)

- **SQLite is retained** — no evidence in the current checkpoint justifies Postgres; a
  single-user desktop tool has no concurrent-writer requirement Postgres would solve
  (ADR-005).
- A lightweight migration runner is **introduced**: a `schema_version` table plus ordered
  `.sql` migration files, run automatically at sidecar startup before the API accepts any
  command — no ORM migration framework is required for this scale.
- The existing repository pattern and parameterized-query discipline are **preserved
  unchanged** beyond the migration wrapper.
- A new table, `ti_results`, is added to store per-provider results (`provider, verdict,
  confidence, raw_payload_json, queried_at`), foreign-keyed to `iocs`, so multi-provider
  results compose additively rather than overwriting one another — this table is the storage
  counterpart of the `ProviderResult` model in `08-threat-intelligence-architecture.md`.

## MIGRATION NOTES

The migration runner must exist and be proven correct **before** any schema change ships —
Master Plan §30.H explicitly warns against introducing it late, after ad-hoc schema drift has
already occurred. This places migration-runner introduction early in Phase 4B/4C rather than
being deferred to whenever the first new table is needed.

## PHASE 4B VERIFICATION (source-verified; supersedes the UNKNOWN section below)

**BEFORE:** "Whether `connection.py` performs any pragma/journaling configuration... UNKNOWN
— VERIFY IN PHASE 4B." / "Confirmed absence of any migration mechanism... currently LIKELY,
not CONFIRMED."

**AFTER:** Direct, full read of `app/database/connection.py` (source of truth) confirms:
- `PRAGMA foreign_keys = ON;` and `PRAGMA journal_mode = WAL;` ARE set on every connection.
- **No `busy_timeout` pragma is set.** This is a new, previously undocumented finding — WAL
  mode reduces but does not eliminate "database is locked" risk without a busy-timeout
  backstop, and the background-thread-write / GUI-thread-read pattern that would trigger
  this risk already exists in the shipped code (`AnalysisWorker` writes on a `QThread` while
  GUI pages read concurrently).
- **No schema-version/migration table exists anywhere in `connection.py` or `repository.py`**
  — the "LIKELY" in the prior version of this document is now **CONFIRMED**.
- `InvestigationRepository` opens/closes a fresh connection per operation via
  `with self._database as connection:` on every method — despite `DatabaseConnection`'s
  shape suggesting a persistent single connection, the actual runtime pattern is
  connection-per-operation. This is favorable, not unfavorable, for the target
  Tauri → Python-sidecar → SQLite model (fewer cross-request state assumptions to carry
  forward).

**REASON:** Phase 4B UNKNOWN #2 (mandatory, phase brief §4).

**SOURCE EVIDENCE:** `app/database/connection.py` (full read, 162 lines),
`app/database/repository.py` (full read, 614 lines). Full detail:
`docs/architecture/PHASE4B_ARCHITECTURAL_FINDINGS.md`.

## UNKNOWN / REQUIRES VERIFICATION (historical — resolved above)

- Whether `app/database/connection.py` performs any pragma/journaling configuration relevant
  to a future multi-process (sidecar) access pattern (e.g. WAL mode, busy-timeout settings).
  ~~UNKNOWN — VERIFY IN PHASE 4B.~~ **RESOLVED — see PHASE 4B VERIFICATION above.**
- Confirmed absence of any existing migration/versioning mechanism — currently **LIKELY**,
  not **CONFIRMED**. ~~VERIFY IN PHASE 4B~~ **RESOLVED — CONFIRMED absent, see above.**

## R2-C Database Persistence Verification

R2-B (see `docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md` and
`tests/test_persistence_paths.py`) established and proved that the
*default* SQLite database path (`app.config.DATABASE_PATH`) resolves
to a persistent, OS-conventional, per-user location via
`platformdirs.user_data_dir()` — independent of CWD, and never under
a PyInstaller `sys._MEIPASS` extraction directory. That work included
one restart-style test using a throwaway `restart_probe` table
created with raw SQL.

R2-C's scope was to prove the stronger, more specific claim: that
**real SOC-IQ application data**, written and read through the
**actual production repository/service stack** (including the real
migration runner), survives both an in-process close/reopen and a
genuine OS process boundary. New tests live in
`tests/test_database_persistence_restart.py`.

### Authoritative database path

Unchanged from R2-B. `app.config.DATABASE_PATH` (=
`APP_DATA_ROOT / "database" / "soc_iq.db"`) is the one authoritative
path. Every production call site that constructs a `DatabaseConnection`
without an explicit `database_path` — `InvestigationRepository`,
`TimelineRepository`, `SystemHealthService` — resolves to this same
default (see the Part I inventory below).

### Initialization / first-run behavior

`DatabaseConnection.connect()` creates its target directory
(`self._database_path.parent.mkdir(parents=True, exist_ok=True)`)
before calling `sqlite3.connect()`, and `run_migrations()`
independently does the same for its own short-lived connection. Both
were exercised in R2-C against a database path whose parent directory
tree did not exist yet
(`test_database_directory_created_on_first_use_via_real_repository`)
— no elevated privileges, no writes outside the target tree.

### Restart behavior — proven at two strengths

1. **In-process close + fresh reconstruction** (Part E): a real
   `Investigation`, saved through `InvestigationRepository.save()`
   (and separately through `InvestigationService.save()`), is
   readable via `get_by_id()` from a brand-new
   `InvestigationRepository`/`InvestigationService` instance
   constructed after the first instance's `DatabaseConnection` was
   explicitly closed. All persisted fields (`report_name`, `iocs`,
   `threat_intelligence`, `risk_score`, `severity`, `confidence`,
   `source_sha256`, `source_size_bytes`) are asserted unchanged.

2. **Real process boundary** (Part F/G): a subprocess (a fresh
   `python -c` interpreter, no shared state with the test process)
   initializes the real repository stack, saves a real
   `Investigation`, commits, and exits. A second, independently
   launched subprocess then re-initializes a repository against the
   same on-disk path and reads the row back. Both processes are
   pointed at the identical `tmp_path`-rooted database file (Part G:
   run #1 path == run #2 path, verified by construction rather than
   by comparing filenames after the fact), and the persisted record
   itself — not merely the file's existence — is asserted.

Both proofs pass. The process-boundary test is the stronger of the
two: no Python object, cache, or interpreter-level state can leak
between the writer and reader subprocess, so it cannot pass by
accident in a way an in-process test theoretically could.

### Schema / migration verification

- `run_migrations()` against a freshly relocated, non-default path
  reaches the same latest schema version as migration discovery
  reports, and is a safe no-op on a second call
  (`test_schema_migrates_to_latest_version_at_a_relocated_path`).
- Constructing `InvestigationRepository` against a brand-new database
  drives the full migration chain (not just the original
  `investigations` table) — verified by confirming
  `timeline_events` (added in migration `0003`) exists afterward
  (`test_repository_construction_triggers_full_migration_chain`).
- The pre-migration-runner bootstrap case described in
  `app/database/migration_runner.py`'s own module docstring (an
  existing `investigations` table with data, no `schema_version`
  table) was reproduced directly and confirmed to upgrade cleanly to
  the latest schema version with the pre-existing row intact and its
  post-`0002` columns (`source_sha256`, `source_size_bytes`) correctly
  `NULL` rather than backfilled
  (`test_pre_migration_runner_database_is_upgraded_without_data_loss`).

No schema or migration file was modified. No defect was found in
commit/transaction behavior — `InvestigationRepository.save()` already
calls `connection.commit()` before returning, and every repository
method uses the `with self._database as connection:` pattern documented
in the Phase 4B verification above.

### Part I — connection/path inventory

| Caller | Connection Mechanism | Path Source | Same Authoritative DB? |
| --- | --- | --- | --- |
| `InvestigationRepository` (`app/database/repository.py`) | `DatabaseConnection()` (default) | `app.config.DATABASE_PATH` | Yes |
| `TimelineRepository` (`app/timeline/repository.py`) | `DatabaseConnection()` (default) | `app.config.DATABASE_PATH` | Yes |
| `SystemHealthService` (`app/services/system_health_service.py`) | `DatabaseConnection()` (default) | `app.config.DATABASE_PATH` | Yes |
| `run_migrations()` (`app/database/migration_runner.py`) | short-lived `sqlite3.connect(database_path)` | caller-supplied `database_path` (always `self._database.database_path`, i.e. the same `DatabaseConnection`'s path, at every production call site) | Yes |

No duplicate or divergent connection mechanism was found. One
implementation subtlety worth recording for future work on this file:
`DatabaseConnection.__init__`'s `database_path: Path = DATABASE_PATH`
default is bound once, at module-import time, per ordinary Python
semantics — reassigning `app.config.DATABASE_PATH` afterward does not
retroactively change that already-bound default. This is not a
production defect (the value is set once, from `APP_DATA_ROOT`, at
process startup, and never reassigned afterward), but it is why the
R2-C Part I test isolates `DatabaseConnection.__init__.__defaults__`
directly rather than patching `app.config.DATABASE_PATH`.

### Remaining limitation

**Real Windows packaged executable persistence has not been tested
here.** All R2-C proofs — including the process-boundary test — run
the genuine, unfrozen `python` interpreter against this source tree.
They prove the database-persistence *contract* is restart-safe at the
application layer; they do not prove behavior inside an actual
PyInstaller-frozen, installed Windows executable across a real OS
reboot/relaunch. That remains explicitly out of scope for R2-C and
belongs to later packaged-runtime verification work (R2-E / R3 / R4).
