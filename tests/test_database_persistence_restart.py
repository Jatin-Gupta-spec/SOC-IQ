"""
R2-C — Database Persistence & Restart Verification.

These tests extend (do not replace) the R2-B proof in
tests/test_persistence_paths.py. R2-B proved that
`DatabaseConnection`'s *default* path resolves to the persistent,
OS-conventional, CWD-independent, non-`_MEIPASS` location, and
demonstrated close/reopen survival with a throwaway
`restart_probe` table created directly via raw SQL.

R2-C proves the stronger, more specific claim required by the R2-C
brief: that a *real* piece of SOC-IQ application data -- an
`Investigation`, written and read through the actual production
`InvestigationRepository`/`InvestigationService` stack (schema
creation via the real migration runner included) -- survives both:

  1. an in-process connection close + fresh reconstruction
     (Part E), and
  2. a real OS process boundary: one Python process writes, exits
     completely, and a second, independently-started Python process
     reads the same row back (Part F).

Every test here uses an isolated `tmp_path`-rooted database file.
None of these tests touch `app.config.DATABASE_PATH`,
`app.config.APP_DATA_ROOT`, or any real per-user or repository
database -- see Part K of the R2-C brief.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================
# Shared helpers
# ==========================================================


def _make_investigation(report_name: str = "r2c-probe-report.txt"):
    """
    Build a real `Investigation` instance using realistic, valid
    field values -- not a synthetic/raw-SQL row -- so the write path
    exercised here is exactly the one `app.analyzer` uses in
    production.
    """

    from app.database.models import Investigation

    return Investigation(
        report_name=report_name,
        iocs={"IPv4": ["203.0.113.42"], "SHA256": ["a" * 64]},
        threat_intelligence={"virustotal": {"malicious": 3}},
        risk_score=72,
        severity="HIGH",
        confidence=0.85,
        ioc_score=40,
        threat_intel_score=20,
        cve_score=12,
        source_sha256="b" * 64,
        source_size_bytes=4096,
    )


# ==========================================================
# Part E -- real write / real read, in-process close + reopen
# ==========================================================


def test_real_investigation_survives_repository_close_and_reopen(
    tmp_path,
):
    """
    Restart-equivalent proof using the real production stack: a
    freshly constructed `InvestigationRepository` (real migration
    runner, real schema, real `DatabaseConnection`) saves a real
    `Investigation`. The repository/connection is then discarded
    entirely and a brand-new `InvestigationRepository` is
    constructed against the same on-disk path, simulating what a
    second application run does. The previously written row must
    still be readable with its important fields unchanged.
    """

    from app.database.connection import DatabaseConnection
    from app.database.repository import InvestigationRepository

    db_path = tmp_path / "database" / "soc_iq.db"
    assert not db_path.exists()

    # --- "run #1" ---
    first_repository = InvestigationRepository(
        database=DatabaseConnection(database_path=db_path)
    )

    written = _make_investigation()
    saved_id = first_repository.save(written)

    # Force the underlying connection closed, mirroring what happens
    # when the application process exits -- do not rely on garbage
    # collection.
    first_repository._database.close()

    assert db_path.exists()

    # --- "run #2": nothing above is reused ---
    second_repository = InvestigationRepository(
        database=DatabaseConnection(database_path=db_path)
    )

    reloaded = second_repository.get_by_id(saved_id)
    second_repository._database.close()

    assert reloaded is not None
    assert reloaded.investigation_id == saved_id
    assert reloaded.report_name == written.report_name
    assert reloaded.iocs == written.iocs
    assert reloaded.threat_intelligence == written.threat_intelligence
    assert reloaded.risk_score == written.risk_score
    assert reloaded.severity == written.severity
    assert reloaded.confidence == written.confidence
    assert reloaded.source_sha256 == written.source_sha256
    assert reloaded.source_size_bytes == written.source_size_bytes


def test_real_investigation_survives_service_layer_close_and_reopen(
    tmp_path,
):
    """
    Same proof as above, one layer up: through
    `InvestigationService`, the actual layer `app.analyzer` and the
    GUI/API call sites use -- not the repository directly.
    """

    from app.database.connection import DatabaseConnection
    from app.database.repository import InvestigationRepository
    from app.database.service import InvestigationService

    db_path = tmp_path / "database" / "soc_iq.db"

    first_service = InvestigationService(
        repository=InvestigationRepository(
            database=DatabaseConnection(database_path=db_path)
        )
    )

    written = _make_investigation(report_name="r2c-service-probe.txt")
    saved_id = first_service.save(written)

    first_service._repository._database.close()

    second_service = InvestigationService(
        repository=InvestigationRepository(
            database=DatabaseConnection(database_path=db_path)
        )
    )

    reloaded = second_service.get_by_id(saved_id)
    second_service._repository._database.close()

    assert reloaded is not None
    assert reloaded.report_name == written.report_name
    assert reloaded.risk_score == written.risk_score


# ==========================================================
# Part F / G -- real process-boundary restart proof
# ==========================================================

_WRITE_SCRIPT = """
import sys
from pathlib import Path
sys.path.insert(0, {project_root!r})

from app.database.connection import DatabaseConnection
from app.database.repository import InvestigationRepository
from app.database.models import Investigation

db_path = Path({db_path!r})

repository = InvestigationRepository(
    database=DatabaseConnection(database_path=db_path)
)

investigation = Investigation(
    report_name="r2c-process-boundary-report.txt",
    iocs={{"Domain": ["evil.example"]}},
    threat_intelligence={{"otx": {{"pulses": 2}}}},
    risk_score=55,
    severity="MEDIUM",
    confidence=0.6,
    ioc_score=25,
    threat_intel_score=15,
    cve_score=15,
    source_sha256="c" * 64,
    source_size_bytes=2048,
)

investigation_id = repository.save(investigation)
repository._database.close()

# Print only the ID, on its own line, so the reader process can
# parse it out of stdout deterministically.
print(investigation_id)
"""

_READ_SCRIPT = """
import sys
from pathlib import Path
sys.path.insert(0, {project_root!r})

from app.database.connection import DatabaseConnection
from app.database.repository import InvestigationRepository

db_path = Path({db_path!r})
investigation_id = {investigation_id!r}

repository = InvestigationRepository(
    database=DatabaseConnection(database_path=db_path)
)

investigation = repository.get_by_id(investigation_id)
repository._database.close()

if investigation is None:
    print("MISSING")
else:
    print("FOUND")
    print(investigation.report_name)
    print(investigation.severity)
    print(investigation.risk_score)
"""


def test_real_investigation_survives_actual_process_boundary(tmp_path):
    """
    The strongest available restart proof: process A initializes the
    real database stack, writes a real `Investigation` through
    `InvestigationRepository`, commits, and exits completely (its
    Python interpreter, its module state, its connection object --
    everything -- is gone). Process B is then launched fresh,
    independently re-initializes the same on-disk database path, and
    must be able to read the row process A wrote.

    This is strictly stronger than an in-process close/reopen test:
    no Python object, cache, or interpreter state can leak between
    process A and process B, so this cannot pass by accident the way
    an in-process test theoretically could if some connection/state
    were not actually being torn down.
    """

    db_path = tmp_path / "database" / "soc_iq.db"

    write_script = _WRITE_SCRIPT.format(
        project_root=str(PROJECT_ROOT),
        db_path=str(db_path),
    )

    write_result = subprocess.run(
        [sys.executable, "-c", write_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert write_result.returncode == 0, write_result.stderr
    assert db_path.exists()

    written_id = int(write_result.stdout.strip().splitlines()[-1])

    read_script = _READ_SCRIPT.format(
        project_root=str(PROJECT_ROOT),
        db_path=str(db_path),
        investigation_id=written_id,
    )

    read_result = subprocess.run(
        [sys.executable, "-c", read_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert read_result.returncode == 0, read_result.stderr

    lines = read_result.stdout.strip().splitlines()

    assert lines[0] == "FOUND"
    assert lines[1] == "r2c-process-boundary-report.txt"
    assert lines[2] == "MEDIUM"
    assert lines[3] == "55"


# ==========================================================
# Part C -- database directory creation from a clean slate
# ==========================================================


def test_database_directory_created_on_first_use_via_real_repository(
    tmp_path,
):
    """
    Part C, exercised through the real repository (not just
    `DatabaseConnection.connect()` in isolation): pointing a fresh
    `InvestigationRepository` at a path whose parent directory tree
    does not exist yet must create it, without elevated privileges,
    and without writing anywhere outside that tree.
    """

    from app.database.connection import DatabaseConnection
    from app.database.repository import InvestigationRepository

    db_path = tmp_path / "does" / "not" / "exist" / "yet" / "soc_iq.db"
    assert not db_path.parent.exists()

    repository = InvestigationRepository(
        database=DatabaseConnection(database_path=db_path)
    )

    repository.save(_make_investigation(report_name="r2c-mkdir-probe.txt"))
    repository._database.close()

    assert db_path.exists()
    assert db_path.parent.is_dir()


# ==========================================================
# Part D -- schema/migration still succeeds against the moved path
# ==========================================================


def test_schema_migrates_to_latest_version_at_a_relocated_path(tmp_path):
    """
    The migration runner must bring a brand-new database at an
    arbitrary (non-default) persistent-style path to the same latest
    schema version it produces at the real default path -- proving
    the physical relocation performed by R2-B did not change
    migration discovery, ordering, or execution.
    """

    from app.database.migration_runner import (
        _discover_migrations,
        MIGRATIONS_DIR,
        run_migrations,
    )

    db_path = tmp_path / "relocated" / "soc_iq.db"

    latest_known = _discover_migrations(MIGRATIONS_DIR)[-1].version

    resulting_version = run_migrations(database_path=db_path)

    assert resulting_version == latest_known

    # Calling it again against the same, now-current database must
    # be a safe no-op that still reports the same version.
    assert run_migrations(database_path=db_path) == latest_known


def test_repository_construction_triggers_full_migration_chain(tmp_path):
    """
    `InvestigationRepository.__init__` must itself drive a brand-new
    database to the latest schema version (it delegates to
    `run_migrations`, see Part D) rather than only creating the
    single `investigations` table -- verified here by confirming the
    `timeline_events` table (added in migration 0003) exists and is
    usable after nothing but constructing the repository.
    """

    from app.database.connection import DatabaseConnection
    from app.database.repository import InvestigationRepository

    db_path = tmp_path / "database" / "soc_iq.db"

    repository = InvestigationRepository(
        database=DatabaseConnection(database_path=db_path)
    )

    with repository._database as connection:
        cursor = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'timeline_events';"
        )
        table_row = cursor.fetchone()

    repository._database.close()

    assert table_row is not None


# ==========================================================
# Part J -- pre-existing ("legacy") database compatibility
# ==========================================================


def test_pre_migration_runner_database_is_upgraded_without_data_loss(
    tmp_path,
):
    """
    Simulates the exact bootstrap case
    `app.database.migration_runner`'s own module docstring describes:
    a database that already contains an `investigations` table (with
    a real row in it) but no `schema_version` table -- i.e. one
    created by a pre-migration-runner build, or one that predates
    R2-B's path relocation. Moving/opening it at a persistent-style
    path must upgrade it to the latest schema version and preserve
    the pre-existing row untouched.
    """

    import sqlite3

    from app.database.connection import DatabaseConnection
    from app.database.migration_runner import _discover_migrations, MIGRATIONS_DIR
    from app.database.repository import InvestigationRepository

    db_path = tmp_path / "legacy" / "soc_iq.db"
    db_path.parent.mkdir(parents=True)

    # Hand-build a pre-migration-runner-era database: only the
    # original (pre-0002, pre-0003) `investigations` shape, no
    # `schema_version` table, with one legacy row already in it.
    legacy_connection = sqlite3.connect(db_path)
    legacy_connection.execute(
        """
        CREATE TABLE investigations (
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
    legacy_connection.execute(
        """
        INSERT INTO investigations (
            report_name, analyzed_at, status, iocs, threat_intelligence,
            risk_score, severity, confidence, ioc_score,
            threat_intel_score, cve_score
        ) VALUES (
            'legacy-report.txt', '2025-01-01T00:00:00+00:00', 'COMPLETED',
            '{}', '{}', 10, 'LOW', 0.2, 5, 3, 2
        );
        """
    )
    legacy_connection.commit()
    legacy_connection.close()

    # Opening the real repository against this pre-existing file must
    # upgrade it, not recreate or wipe it.
    repository = InvestigationRepository(
        database=DatabaseConnection(database_path=db_path)
    )

    legacy_investigation = repository.get_by_id(1)
    repository._database.close()

    assert legacy_investigation is not None
    assert legacy_investigation.report_name == "legacy-report.txt"
    # Columns added by 0002 must be present and NULL (never
    # backfilled/fabricated) on a row written before that migration.
    assert legacy_investigation.source_sha256 is None
    assert legacy_investigation.source_size_bytes is None

    latest_known = _discover_migrations(MIGRATIONS_DIR)[-1].version

    verify_connection = sqlite3.connect(db_path)
    version_row = verify_connection.execute(
        "SELECT version FROM schema_version;"
    ).fetchone()
    verify_connection.close()

    assert version_row[0] == latest_known


# ==========================================================
# Part I -- every production connection agrees on one authoritative path
# ==========================================================


@pytest.mark.parametrize(
    "database_path",
    [
        pytest.param(
            "database/soc_iq.db",
            id="repository",
        ),
    ],
)
def test_repository_and_timeline_repository_share_one_database_path(
    tmp_path, monkeypatch, database_path
):
    """
    Part I inventory, exercised rather than merely inspected:
    `InvestigationRepository` and `TimelineRepository` (the two
    production repositories that each default their own
    `DatabaseConnection()` independently -- see app/database/
    repository.py and app/timeline/repository.py) must resolve to
    the exact same on-disk file when neither is given an explicit
    `database=` argument, since both defaults trace back to the same
    `app.config.DATABASE_PATH`.
    """

    from app.database.connection import DatabaseConnection
    from app.database.repository import InvestigationRepository
    from app.timeline.repository import TimelineRepository

    isolated_path = tmp_path / database_path

    # `DatabaseConnection.__init__`'s `database_path: Path =
    # DATABASE_PATH` default is bound once, at class-definition
    # (import) time -- a standard Python behavior, not an R2-C
    # defect. Reassigning `app.config.DATABASE_PATH` (or even
    # `app.database.connection.DATABASE_PATH`) afterward does *not*
    # change what already-bound default, because Python captures the
    # default value itself, not a reference to the name. The correct
    # way to isolate what every default-constructed
    # `DatabaseConnection()` resolves to is therefore to replace the
    # bound default directly, which is exactly what every real
    # default-constructed `DatabaseConnection()` call site
    # (`InvestigationRepository`, `TimelineRepository`,
    # `system_health_service.py`) actually goes through.
    monkeypatch.setattr(
        DatabaseConnection.__init__,
        "__defaults__",
        (isolated_path,),
    )

    investigation_repository = InvestigationRepository()
    timeline_repository = TimelineRepository()

    try:
        assert (
            investigation_repository._database.database_path
            == isolated_path
        )
        assert (
            timeline_repository._database.database_path == isolated_path
        )
    finally:
        investigation_repository._database.close()
        timeline_repository._database.close()
