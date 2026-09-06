"""
Database/migration tests for the timeline_events table
(Phase A4-P2-P3, Part 1/6).

Covers: fresh-database migration, existing-database migration
safety, persistence across connection reopen, and foreign-key /
ordering behavior at the raw-SQL level (repository-level behavior
is covered separately in tests/test_timeline_repository.py).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from app.database.connection import DatabaseConnection
from app.database.migration_runner import run_migrations
from app.database.repository import InvestigationRepository
from app.database.models import Investigation


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="report.txt",
        iocs={},
        threat_intelligence={},
        risk_score=1,
        severity="LOW",
        confidence=0.1,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "timeline_test.db"


# ==========================================================
# Fresh database
# ==========================================================


def test_migration_on_fresh_database_creates_table_and_index(db_path):
    run_migrations(database_path=db_path)

    connection = sqlite3.connect(db_path)

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        )
    }
    assert "timeline_events" in tables

    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index';"
        )
    }
    assert "idx_timeline_events_investigation_timestamp" in indexes

    version = connection.execute(
        "SELECT MAX(version) FROM schema_version;"
    ).fetchone()[0]
    # Latest schema version as of MAX-21B-2 (F2 fix,
    # 0004_unique_report_name.sql) -- was 3 prior to that migration.
    assert version == 4

    connection.close()


def test_fresh_migration_is_idempotent(db_path):
    run_migrations(database_path=db_path)
    # Running again against an already-current database must be a
    # safe no-op, not an error.
    run_migrations(database_path=db_path)


# ==========================================================
# Existing database
# ==========================================================


def test_migration_preserves_existing_investigations(db_path):
    connection = DatabaseConnection(database_path=db_path)
    repo = InvestigationRepository(database=connection)

    inv_id = repo.save(make_investigation(report_name="pre-existing.txt"))
    connection.close()

    # Re-run migrations explicitly (simulates a later app startup
    # against this now-existing database).
    run_migrations(database_path=db_path)

    connection2 = DatabaseConnection(database_path=db_path)
    repo2 = InvestigationRepository(database=connection2)
    fetched = repo2.get_by_id(inv_id)
    connection2.close()

    assert fetched is not None
    assert fetched.report_name == "pre-existing.txt"


def test_timeline_table_added_safely_without_touching_investigations(db_path):
    # Simulate a database that predates the timeline migration: build
    # it by hand at schema version 2 (investigations only, as
    # 0001+0002 leave it), bypassing the shared runner so 0003 is not
    # yet applied -- this is what a real pre-Part-1 database on disk
    # looks like.
    raw = sqlite3.connect(db_path)
    raw.execute(
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
            cve_score INTEGER NOT NULL,
            source_sha256 TEXT NULL,
            source_size_bytes INTEGER NULL
        );
        """
    )
    raw.execute(
        "INSERT INTO investigations "
        "(report_name, analyzed_at, status, iocs, threat_intelligence, "
        "risk_score, severity, confidence, ioc_score, threat_intel_score, "
        "cve_score) VALUES "
        "('legacy.txt', '2025-01-01T00:00:00+00:00', 'COMPLETED', "
        "'{}', '{}', 1, 'LOW', 0.1, 0, 0, 0);"
    )
    raw.execute(
        "CREATE TABLE schema_version (version INTEGER NOT NULL);"
    )
    raw.execute("INSERT INTO schema_version VALUES (2);")
    raw.commit()

    before_tables = {
        row[0]
        for row in raw.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        )
    }
    before_investigation_count = raw.execute(
        "SELECT COUNT(*) FROM investigations;"
    ).fetchone()[0]
    raw.close()
    assert "timeline_events" not in before_tables

    run_migrations(database_path=db_path)

    raw2 = sqlite3.connect(db_path)
    after_tables = {
        row[0]
        for row in raw2.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        )
    }
    after_investigation_count = raw2.execute(
        "SELECT COUNT(*) FROM investigations;"
    ).fetchone()[0]
    legacy_row = raw2.execute(
        "SELECT report_name FROM investigations WHERE report_name = 'legacy.txt';"
    ).fetchone()
    raw2.close()

    assert "timeline_events" in after_tables
    assert before_tables <= after_tables  # nothing removed
    assert after_investigation_count == before_investigation_count
    assert legacy_row is not None  # pre-existing row untouched


# ==========================================================
# Insert / retrieve / foreign key / ordering (raw SQL level)
# ==========================================================


@pytest.fixture()
def populated_db(db_path):
    connection = DatabaseConnection(database_path=db_path)
    repo = InvestigationRepository(database=connection)
    inv_id = repo.save(make_investigation())
    connection.close()
    return db_path, inv_id


def test_insert_and_retrieve_timeline_event(populated_db):
    db_path, inv_id = populated_db

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        INSERT INTO timeline_events (
            event_id, investigation_id, event_type,
            timestamp, source, summary, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "evt-1",
            inv_id,
            "analysis.completed",
            "2026-01-01T00:00:00+00:00",
            "system",
            "Analysis finished.",
            json.dumps({"ioc_count": 3}),
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT event_id, summary, metadata FROM timeline_events "
        "WHERE event_id = ?;",
        ("evt-1",),
    ).fetchone()
    conn.close()

    assert row[0] == "evt-1"
    assert row[1] == "Analysis finished."
    assert json.loads(row[2]) == {"ioc_count": 3}


def test_foreign_key_rejects_nonexistent_investigation(populated_db):
    db_path, _inv_id = populated_db

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO timeline_events (
                event_id, investigation_id, event_type,
                timestamp, source, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "evt-orphan",
                999999,
                "analysis.completed",
                "2026-01-01T00:00:00+00:00",
                "system",
                "x",
                None,
            ),
        )
        conn.commit()

    conn.close()


def test_check_constraint_rejects_unknown_event_type(populated_db):
    db_path, inv_id = populated_db

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO timeline_events (
                event_id, investigation_id, event_type,
                timestamp, source, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "evt-bad-type",
                inv_id,
                "malware.executed",
                "2026-01-01T00:00:00+00:00",
                "system",
                "x",
                None,
            ),
        )
        conn.commit()

    conn.close()


def test_equal_timestamps_ordered_by_insertion_order(populated_db):
    db_path, inv_id = populated_db

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    same_ts = "2026-01-01T00:00:00+00:00"
    for event_id, summary in (
        ("evt-a", "first"),
        ("evt-b", "second"),
        ("evt-c", "third"),
    ):
        conn.execute(
            """
            INSERT INTO timeline_events (
                event_id, investigation_id, event_type,
                timestamp, source, summary, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (event_id, inv_id, "analysis.started", same_ts, "system", summary, None),
        )
    conn.commit()

    rows = conn.execute(
        "SELECT summary FROM timeline_events "
        "WHERE investigation_id = ? "
        "ORDER BY timestamp ASC, rowid ASC;",
        (inv_id,),
    ).fetchall()
    conn.close()

    assert [row[0] for row in rows] == ["first", "second", "third"]


def test_persistence_across_connection_reopen(populated_db):
    db_path, inv_id = populated_db

    conn1 = sqlite3.connect(db_path)
    conn1.execute("PRAGMA foreign_keys = ON;")
    conn1.execute(
        """
        INSERT INTO timeline_events (
            event_id, investigation_id, event_type,
            timestamp, source, summary, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "evt-persist",
            inv_id,
            "investigation.created",
            "2026-01-01T00:00:00+00:00",
            "system",
            "created",
            None,
        ),
    )
    conn1.commit()
    conn1.close()

    conn2 = sqlite3.connect(db_path)
    row = conn2.execute(
        "SELECT summary FROM timeline_events WHERE event_id = ?;",
        ("evt-persist",),
    ).fetchone()
    conn2.close()

    assert row[0] == "created"
