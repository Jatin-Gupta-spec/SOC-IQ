"""
Regression tests for app.database.migration_runner.

Covers: fresh-database bootstrap, bootstrap against a pre-existing
(pre-migration-runner) database with real data, repeat-execution
idempotency, sequential multi-migration ordering, failed-migration
rollback and atomicity, fail-closed behavior against an unknown
future schema version, malformed/duplicate migration file rejection,
a missing migrations directory, end-to-end startup through
InvestigationRepository, (Phase A4-P2 Part 2 migration-verification
closure) the full pre-provenance -> current-schema migration path:
a genuinely pre-0002/0003 database with a real legacy investigation,
migrated through the actual runner and the actual migration files,
verified at the domain/repository level -- not just raw SQL -- to
confirm the legacy row's provenance fields read back as unavailable
while newly-saved investigations in the same, now-migrated database
persist and retrieve real provenance correctly, and (F-21B4E-01)
concurrent-caller safety: multiple threads invoking migration
initialization against the same pre-upgrade database can no longer
race each other into applying already-committed DDL a second time.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.database.migration_runner import (
    MigrationError,
    run_migrations,
)
from app.database.repository import InvestigationRepository
from app.database.connection import DatabaseConnection
from app.database.models import Investigation


# ==========================================================
# Helpers
# ==========================================================


def write_migration(
    migrations_dir: Path,
    filename: str,
    sql: str,
) -> None:
    migrations_dir.mkdir(parents=True, exist_ok=True)
    (migrations_dir / filename).write_text(sql, encoding="utf-8")


def real_migrations_dir() -> Path:
    """
    The project's actual, shipped migrations directory
    (app/database/migrations/), used for tests that must exercise the
    real 0001_initial.sql rather than synthetic test-only migrations.
    """

    return (
        Path(__file__).resolve().parent.parent
        / "app"
        / "database"
        / "migrations"
    )


def create_pre_migration_database(db_path: Path) -> None:
    """
    Build a database exactly the way the pre-migration-runner
    InvestigationRepository used to: an `investigations` table, no
    `schema_version` table at all. This is the bootstrap scenario.
    """

    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)

    try:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_name TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                status TEXT NOT NULL,
                iocs TEXT NOT NULL,
                threat_intelligence TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                ioc_score INTEGER NOT NULL,
                threat_intel_score INTEGER NOT NULL,
                cve_score INTEGER NOT NULL
            );
            """
        )

        connection.commit()

    finally:

        connection.close()


def insert_investigation(
    db_path: Path,
    report_name: str,
) -> int:

    connection = sqlite3.connect(db_path)

    try:

        cursor = connection.execute(
            """
            INSERT INTO investigations (
                report_name, analyzed_at, status, iocs,
                threat_intelligence, risk_score, severity,
                confidence, ioc_score, threat_intel_score, cve_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                report_name,
                datetime.now(UTC).isoformat(),
                "COMPLETED",
                json.dumps({"ipv4": ["1.2.3.4"]}),
                json.dumps({"status": "ok"}),
                42,
                "MEDIUM",
                0.75,
                10,
                0,
                0,
            ),
        )

        connection.commit()

        row_id = cursor.lastrowid

    finally:

        connection.close()

    assert row_id is not None

    return row_id


# ==========================================================
# 1. Fresh database
# ==========================================================


def test_fresh_database_migrates_to_latest(tmp_path):

    db_path = tmp_path / "fresh.db"

    version = run_migrations(
        database_path=db_path,
        migrations_dir=real_migrations_dir(),
    )

    # Latest schema version as of MAX-21B-2 (F2 fix,
    # 0004_unique_report_name.sql) -- was 3 prior to that migration.
    assert version == 4

    connection = sqlite3.connect(db_path)

    try:

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        assert "investigations" in tables
        assert "schema_version" in tables

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
        assert recorded_version == 4

    finally:

        connection.close()


# ==========================================================
# 2. Existing (pre-migration-runner) database -- bootstrap
# ==========================================================


def test_bootstrap_preserves_existing_data(tmp_path):

    db_path = tmp_path / "existing.db"

    create_pre_migration_database(db_path)

    inserted_ids = [
        insert_investigation(db_path, f"report_{i}.txt")
        for i in range(5)
    ]

    version = run_migrations(
        database_path=db_path,
        migrations_dir=real_migrations_dir(),
    )

    # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
    assert version == 4

    connection = sqlite3.connect(db_path)

    try:

        row_count = connection.execute(
            "SELECT COUNT(*) FROM investigations;"
        ).fetchone()[0]

        assert row_count == 5

        report_names = {
            row[0]
            for row in connection.execute(
                "SELECT report_name FROM investigations;"
            )
        }

        assert report_names == {
            f"report_{i}.txt" for i in range(5)
        }

        ids_present = {
            row[0]
            for row in connection.execute(
                "SELECT id FROM investigations;"
            )
        }

        assert ids_present == set(inserted_ids)

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
        assert recorded_version == 4

    finally:

        connection.close()


# ==========================================================
# 3. Already-current database: repeat execution
# ==========================================================


def test_repeat_execution_is_noop(tmp_path):

    db_path = tmp_path / "repeat.db"

    first = run_migrations(
        database_path=db_path,
        migrations_dir=real_migrations_dir(),
    )

    second = run_migrations(
        database_path=db_path,
        migrations_dir=real_migrations_dir(),
    )

    third = run_migrations(
        database_path=db_path,
        migrations_dir=real_migrations_dir(),
    )

    # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
    assert first == 4
    assert second == 4
    assert third == 4

    connection = sqlite3.connect(db_path)

    try:

        version_rows = connection.execute(
            "SELECT COUNT(*) FROM schema_version;"
        ).fetchone()[0]

        assert version_rows == 1

    finally:

        connection.close()


def test_repeat_execution_does_not_reapply_migration_side_effects(
    tmp_path,
):
    """
    A migration that has an observable side effect (here: inserting a
    marker row) must only ever run once, even across repeated calls
    to run_migrations.
    """

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_marker.sql",
        """
        CREATE TABLE marker (id INTEGER PRIMARY KEY);
        INSERT INTO marker (id) VALUES (1);
        """,
    )

    db_path = tmp_path / "marker.db"

    run_migrations(database_path=db_path, migrations_dir=migrations_dir)
    run_migrations(database_path=db_path, migrations_dir=migrations_dir)
    run_migrations(database_path=db_path, migrations_dir=migrations_dir)

    connection = sqlite3.connect(db_path)

    try:

        marker_rows = connection.execute(
            "SELECT COUNT(*) FROM marker;"
        ).fetchone()[0]

        assert marker_rows == 1

    finally:

        connection.close()


# ==========================================================
# 4. Sequential migration execution
# ==========================================================


def test_sequential_migrations_apply_in_order(tmp_path):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_create_a.sql",
        "CREATE TABLE a (id INTEGER PRIMARY KEY);",
    )
    write_migration(
        migrations_dir,
        "0002_create_b.sql",
        "CREATE TABLE b (id INTEGER PRIMARY KEY);",
    )
    write_migration(
        migrations_dir,
        "0003_create_c.sql",
        "CREATE TABLE c (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "sequential.db"

    version = run_migrations(
        database_path=db_path,
        migrations_dir=migrations_dir,
    )

    assert version == 3

    connection = sqlite3.connect(db_path)

    try:

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        assert {"a", "b", "c", "schema_version"} <= tables

    finally:

        connection.close()


def test_sequential_migrations_resume_from_current_version(tmp_path):
    """
    A database already at version 1 must only apply 0002 and 0003 on
    the next call, not re-apply 0001.
    """

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_create_a.sql",
        "CREATE TABLE a (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "resume.db"

    run_migrations(database_path=db_path, migrations_dir=migrations_dir)

    write_migration(
        migrations_dir,
        "0002_create_b.sql",
        "CREATE TABLE b (id INTEGER PRIMARY KEY);",
    )

    version = run_migrations(
        database_path=db_path,
        migrations_dir=migrations_dir,
    )

    assert version == 2


# ==========================================================
# 5. Failed migration: rollback and atomicity
# ==========================================================


def test_failed_migration_rolls_back_and_version_unchanged(tmp_path):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_good.sql",
        "CREATE TABLE good (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "failed.db"

    run_migrations(database_path=db_path, migrations_dir=migrations_dir)

    # Only introduce the failing migration after the database is
    # already at version 1 -- this test is specifically about a
    # migration that fails on top of a prior successful one, not
    # about the first migration in a fresh database failing.
    write_migration(
        migrations_dir,
        "0002_bad.sql",
        "THIS IS NOT VALID SQL;",
    )

    with pytest.raises(MigrationError):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )

    connection = sqlite3.connect(db_path)

    try:

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        assert recorded_version == 1

    finally:

        connection.close()


def test_failed_migration_does_not_leave_partial_ddl(tmp_path):
    """
    A migration with two statements, where the second fails, must
    leave neither statement's effect behind -- the whole migration is
    one transaction.
    """

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_partial.sql",
        """
        CREATE TABLE first_table (id INTEGER PRIMARY KEY);
        THIS IS NOT VALID SQL;
        """,
    )

    db_path = tmp_path / "partial.db"

    with pytest.raises(MigrationError):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )

    connection = sqlite3.connect(db_path)

    try:

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        # Neither the successfully-parsed first statement's table nor
        # a schema_version row should have survived the rollback.
        assert "first_table" not in tables

        has_version_row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'schema_version';"
        ).fetchone()[0]

        if has_version_row:

            count = connection.execute(
                "SELECT COUNT(*) FROM schema_version;"
            ).fetchone()[0]

            assert count == 0

    finally:

        connection.close()


def test_application_refuses_to_continue_after_failed_migration(
    tmp_path,
):
    """
    run_migrations must raise -- not return a version, not log and
    swallow the error -- so that any caller (e.g. repository
    construction) is forced to stop rather than continue against a
    partially migrated schema.
    """

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_bad.sql",
        "NOT VALID SQL AT ALL;",
    )

    db_path = tmp_path / "refuse.db"

    with pytest.raises(MigrationError):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )


# ==========================================================
# 6. Unknown future version: fail closed
# ==========================================================


def test_unknown_future_version_fails_closed(tmp_path):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_create_a.sql",
        "CREATE TABLE a (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "future.db"

    # Seed a database that claims to already be at version 999.
    connection = sqlite3.connect(db_path)

    try:

        connection.execute(
            "CREATE TABLE schema_version (version INTEGER NOT NULL);"
        )
        connection.execute(
            "INSERT INTO schema_version (version) VALUES (999);"
        )
        connection.commit()

    finally:

        connection.close()

    with pytest.raises(MigrationError):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )

    # Confirm nothing was silently changed: version is still 999,
    # table "a" was never created.
    connection = sqlite3.connect(db_path)

    try:

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        assert recorded_version == 999

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        assert "a" not in tables

    finally:

        connection.close()


# ==========================================================
# 7. Duplicate migration version
# ==========================================================


def test_duplicate_migration_version_raises(tmp_path):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_first.sql",
        "CREATE TABLE first_one (id INTEGER PRIMARY KEY);",
    )
    write_migration(
        migrations_dir,
        "0001_second.sql",
        "CREATE TABLE second_one (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "duplicate.db"

    with pytest.raises(MigrationError, match="Duplicate"):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )


# ==========================================================
# 8. Malformed migration filename
# ==========================================================


@pytest.mark.parametrize(
    "filename",
    [
        "not_a_migration.sql",
        "1_too_few_digits.sql",
        "00001_too_many_digits.sql",
        "0001-wrong-separator.sql",
    ],
)
def test_malformed_migration_filename_raises(tmp_path, filename):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        filename,
        "CREATE TABLE whatever (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "malformed.db"

    with pytest.raises(MigrationError, match="Malformed"):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )


# ==========================================================
# 9. Missing migrations directory
# ==========================================================


def test_missing_migrations_directory_raises(tmp_path):

    db_path = tmp_path / "no_migrations_dir.db"

    with pytest.raises(MigrationError, match="not found"):
        run_migrations(
            database_path=db_path,
            migrations_dir=tmp_path / "does_not_exist",
        )


# ==========================================================
# 10. Migration atomicity (schema + version bump together)
# ==========================================================


def test_version_only_advances_on_full_success(tmp_path):

    migrations_dir = tmp_path / "migrations"

    write_migration(
        migrations_dir,
        "0001_ok.sql",
        "CREATE TABLE ok_table (id INTEGER PRIMARY KEY);",
    )

    db_path = tmp_path / "atomic.db"

    version = run_migrations(
        database_path=db_path,
        migrations_dir=migrations_dir,
    )

    assert version == 1

    write_migration(
        migrations_dir,
        "0002_broken.sql",
        "SYNTAX ERROR HERE;",
    )

    with pytest.raises(MigrationError):
        run_migrations(
            database_path=db_path,
            migrations_dir=migrations_dir,
        )

    connection = sqlite3.connect(db_path)

    try:

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        # Still 1 -- the failed migration 0002 never advanced it.
        assert recorded_version == 1

    finally:

        connection.close()


# ==========================================================
# 11. End-to-end: repository construction goes through the runner
# ==========================================================


def test_repository_construction_bootstraps_schema(tmp_path):

    db_path = tmp_path / "repo.db"

    database = DatabaseConnection(database_path=db_path)

    InvestigationRepository(database=database)

    connection = sqlite3.connect(db_path)

    try:

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        assert "investigations" in tables
        assert "schema_version" in tables

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
        assert recorded_version == 4

    finally:

        connection.close()


def test_repository_construction_against_existing_database_preserves_data(
    tmp_path,
):
    """
    Constructing a repository against a database that already
    contains investigations (created before the migration runner
    existed) must not lose that data.
    """

    db_path = tmp_path / "existing_repo.db"

    create_pre_migration_database(db_path)
    insert_investigation(db_path, "pre_existing_report.txt")

    database = DatabaseConnection(database_path=db_path)

    repository = InvestigationRepository(database=database)

    investigations = repository.list_all()

    assert len(investigations) == 1
    assert investigations[0].report_name == "pre_existing_report.txt"


# ==========================================================
# 12. Legacy -> current schema: provenance migration path
#     (Phase A4-P2 Part 2 -- migration-verification closure)
#
# The tests above (10, 11) already prove that a pre-migration-runner
# database survives the migration and that its rows are not lost.
# What they do not prove -- and what this section adds -- is that,
# *after* the real 0002/0003 migrations have actually run against a
# real legacy row, that row's new provenance columns read back through
# the domain/repository layer (not raw SQL) as the explicit
# "unavailable" state (`None`/`None`), never a fabricated hash, and
# that a brand-new investigation saved afterward in that same,
# now-migrated database persists and retrieves real provenance
# correctly and in isolation from the legacy row.
# ==========================================================


def test_legacy_investigation_has_unavailable_provenance_after_migration(
    tmp_path,
):
    """
    A database created before source provenance existed (schema
    version 0: `investigations` only, no `schema_version` table --
    see `create_pre_migration_database`) is migrated through the
    real, shipped migration chain (0001 -> 0002 -> 0003). The legacy
    row must remain fully readable, keep its original ID and all
    pre-existing field values unchanged, and its new
    `source_sha256` / `source_size_bytes` columns must read back as
    `None` -- the honest "never calculated" state
    `Investigation.source_sha256` documents -- never `NULL` coerced
    to a placeholder, and never a hash invented for bytes SOC-IQ no
    longer has.
    """

    db_path = tmp_path / "legacy_provenance.db"

    create_pre_migration_database(db_path)

    legacy_id = insert_investigation(db_path, "legacy_malware_report.txt")

    # The real migration mechanism -- not a hand-written ALTER TABLE
    # in this test -- via the same path production code uses
    # (InvestigationRepository -> _initialize_database -> run_migrations
    # against app/database/migrations/).
    database = DatabaseConnection(database_path=db_path)
    repository = InvestigationRepository(database=database)

    # Schema reaches the current version (4 as of MAX-21B-2's F2 fix --
    # see test_fresh_database_migrates_to_latest). Read directly from
    # schema_version, independent of the repository, so this assertion
    # does not merely restate what the repository already assumes.
    raw_connection = sqlite3.connect(db_path)
    try:
        recorded_version = raw_connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]
        assert recorded_version == 4
    finally:
        raw_connection.close()

    legacy = repository.get_by_id(legacy_id)

    assert legacy is not None
    assert legacy.investigation_id == legacy_id
    assert legacy.report_name == "legacy_malware_report.txt"

    # Pre-existing fields survive the migration completely unchanged.
    assert legacy.status == "COMPLETED"
    assert legacy.iocs == {"ipv4": ["1.2.3.4"]}
    assert legacy.threat_intelligence == {"status": "ok"}
    assert legacy.risk_score == 42
    assert legacy.severity == "MEDIUM"
    assert legacy.confidence == 0.75
    assert legacy.ioc_score == 10

    # The provenance gap this test exists to close: read through the
    # domain object, not raw SQL, the legacy row's provenance is
    # explicitly unavailable -- never fabricated.
    assert legacy.source_sha256 is None
    assert legacy.source_size_bytes is None


def test_new_investigation_persists_real_provenance_after_legacy_migration(
    tmp_path,
):
    """
    After a pre-provenance database with a real legacy row has been
    migrated to the current schema, a *new* investigation saved
    through the normal repository path must persist and retrieve its
    source SHA-256 and size correctly, and the two investigations
    (one with no provenance, one with real provenance) must remain
    isolated from each other in the same database.
    """

    db_path = tmp_path / "legacy_then_new.db"

    create_pre_migration_database(db_path)
    legacy_id = insert_investigation(db_path, "legacy_report.txt")

    database = DatabaseConnection(database_path=db_path)
    repository = InvestigationRepository(database=database)

    new_investigation = Investigation(
        report_name="freshly_analyzed_report.txt",
        iocs={"ipv4": ["9.9.9.9"]},
        threat_intelligence={"status": "ok"},
        risk_score=88,
        severity="HIGH",
        confidence=0.95,
        ioc_score=20,
        threat_intel_score=15,
        cve_score=5,
        source_sha256="f" * 64,
        source_size_bytes=2048,
    )

    new_id = repository.save(new_investigation)

    assert new_id != legacy_id

    fetched_new = repository.get_by_id(new_id)
    assert fetched_new is not None
    assert fetched_new.source_sha256 == "f" * 64
    assert fetched_new.source_size_bytes == 2048

    # The legacy row is untouched by the new save -- still explicitly
    # unavailable, not accidentally backfilled or overwritten.
    fetched_legacy = repository.get_by_id(legacy_id)
    assert fetched_legacy is not None
    assert fetched_legacy.source_sha256 is None
    assert fetched_legacy.source_size_bytes is None

    all_investigations = repository.list_all()
    assert len(all_investigations) == 2


# ==========================================================
# 13. Concurrent migration initialization (F-21B4E-01)
#
# Root cause: the pending-migration list used to be computed once,
# from a schema version read *before* any write lock was acquired,
# and then applied blindly. A second caller could commit one of
# those same migrations in the window between that read and this
# connection's BEGIN IMMEDIATE, so this connection would go on to
# attempt DDL (e.g. `ALTER TABLE ... ADD COLUMN`) that had already
# been committed, surfacing as `sqlite3.OperationalError: duplicate
# column name` wrapped in a `MigrationError`. The fix re-reads the
# schema version fresh, under the write lock, before deciding which
# single migration (if any) is still pending -- one migration per
# `BEGIN IMMEDIATE`/`COMMIT` cycle -- so a migration is only ever
# applied if it is still pending *after* this connection holds the
# lock.
# ==========================================================


def _run_concurrent_migration_race(
    db_path: Path,
    migrations_dir: Path,
    thread_count: int,
) -> tuple[list[str], list[threading.Thread]]:
    """
    Start `thread_count` threads, release them at (as close to) the
    same moment as possible via a barrier, and have every one of them
    call `run_migrations` against the *same* `db_path`. Returns the
    list of exception reprs raised by any thread (empty means every
    caller completed successfully) and the thread objects themselves
    (so the caller can assert none are still alive, i.e. no hang).

    A barrier is used rather than relying on incidental OS/GIL
    scheduling alone, per the deterministic-race requirement: every
    thread is held at the same starting line and released together,
    so all of them contend for SQLite's write lock at effectively the
    same time on every run, instead of the race only sometimes being
    exercised.
    """

    errors: list[str] = []
    errors_lock = threading.Lock()
    start_barrier = threading.Barrier(thread_count)

    def worker() -> None:

        try:
            start_barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            with errors_lock:
                errors.append("barrier aborted: a peer thread failed")
            return

        try:
            run_migrations(
                database_path=db_path,
                migrations_dir=migrations_dir,
            )
        except Exception as exc:
            with errors_lock:
                errors.append(repr(exc))
            # A failure here must never strand every other thread at
            # a barrier in a *later* iteration/test -- this barrier
            # is already past its wait, so nothing to abort, but keep
            # the pattern explicit for anyone extending this helper.

    threads = [
        threading.Thread(target=worker) for _ in range(thread_count)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=15)

    return errors, threads


def test_concurrent_migration_from_fresh_database_converges_safely(
    tmp_path,
):
    """
    The required regression scenario: a database below the latest
    migration (here, a brand-new database at version 0), with
    multiple callers concurrently invoking migration initialization
    against it. No caller may receive a `MigrationError` caused by
    duplicate DDL, no caller may hang, every caller must complete,
    and the database must converge on the correct final schema with
    every migration applied exactly once.
    """

    db_path = tmp_path / "concurrent_fresh.db"
    migrations_dir = real_migrations_dir()

    errors, threads = _run_concurrent_migration_race(
        db_path=db_path,
        migrations_dir=migrations_dir,
        thread_count=10,
    )

    assert not any(thread.is_alive() for thread in threads), (
        "a caller hung instead of completing"
    )
    assert errors == [], (
        "a concurrent caller failed instead of converging safely: "
        f"{errors}"
    )

    connection = sqlite3.connect(db_path)

    try:

        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]

        # See test_fresh_database_migrates_to_latest re: version 3 -> 4.
        assert recorded_version == 4

        version_rows = connection.execute(
            "SELECT COUNT(*) FROM schema_version;"
        ).fetchone()[0]

        # Exactly one version row -- no caller's race duplicated it.
        assert version_rows == 1

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }

        assert {"investigations", "schema_version"} <= tables

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(investigations);"
            )
        }

        # Every migration actually landed -- not just the version
        # counter advancing without the corresponding DDL.
        assert "source_sha256" in columns
        assert "source_size_bytes" in columns

    finally:

        connection.close()


def test_concurrent_migration_from_partially_migrated_database_converges_safely(
    tmp_path,
):
    """
    Same required scenario, but starting from a database already
    partway through the migration chain (version 1) rather than from
    scratch -- the original defect report's exact reproduction shape
    (a database below the latest migration, multiple concurrent
    callers). Confirms the fix isn't specific to racing from version
    0.
    """

    db_path = tmp_path / "concurrent_partial.db"
    migrations_dir = real_migrations_dir()

    # Bring the database to version 1 single-threaded first.
    write_migration(
        tmp_path / "seed_migrations",
        "0001_initial.sql",
        (migrations_dir / "0001_initial.sql").read_text(encoding="utf-8"),
    )
    run_migrations(
        database_path=db_path,
        migrations_dir=tmp_path / "seed_migrations",
    )

    connection = sqlite3.connect(db_path)
    try:
        seeded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]
    finally:
        connection.close()
    assert seeded_version == 1

    errors, threads = _run_concurrent_migration_race(
        db_path=db_path,
        migrations_dir=migrations_dir,
        thread_count=10,
    )

    assert not any(thread.is_alive() for thread in threads)
    assert errors == [], errors

    connection = sqlite3.connect(db_path)
    try:
        recorded_version = connection.execute(
            "SELECT version FROM schema_version;"
        ).fetchone()[0]
        assert recorded_version == 4
    finally:
        connection.close()


def test_concurrent_migration_race_repeated_iterations(tmp_path):
    """
    A single race outcome is weak evidence on its own -- thread
    scheduling can happen to serialize even when a real race
    condition exists. Repeat the fresh-database race scenario many
    times in independent temporary databases and require a clean
    result on every single iteration: 0 migration failures, 0 hangs,
    across all of them.
    """

    migrations_dir = real_migrations_dir()
    iterations = 25
    thread_count = 8

    failures: list[str] = []
    hangs = 0

    for iteration in range(iterations):

        db_path = tmp_path / f"iter_{iteration}.db"

        errors, threads = _run_concurrent_migration_race(
            db_path=db_path,
            migrations_dir=migrations_dir,
            thread_count=thread_count,
        )

        if any(thread.is_alive() for thread in threads):
            hangs += 1

        if errors:
            failures.append(f"iteration {iteration}: {errors}")
            continue

        connection = sqlite3.connect(db_path)
        try:
            recorded_version = connection.execute(
                "SELECT version FROM schema_version;"
            ).fetchone()[0]
        finally:
            connection.close()

        if recorded_version != 4:
            failures.append(
                f"iteration {iteration}: wrong final version "
                f"{recorded_version}"
            )

    assert hangs == 0, f"{hangs}/{iterations} iterations hung"
    assert failures == [], (
        f"{len(failures)}/{iterations} iterations failed: {failures}"
    )
