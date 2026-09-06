"""
Regression tests for the SOC-IQ database layer:
app.database.connection, app.database.repository, and
app.database.service.

Covers connection lifecycle, repository CRUD, InvestigationService
delegation, persistence across connections, and error handling for
malformed/corrupted rows.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from app.database.connection import DatabaseConnection
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.database.service import InvestigationService


# ==========================================================
# Helpers
# ==========================================================


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="malware_report.txt",
        iocs={"ipv4": ["1.2.3.4"], "domains": ["evil.example"]},
        threat_intelligence={"status": "ok", "hashes": []},
        risk_score=42,
        severity="MEDIUM",
        confidence=0.75,
        ioc_score=10,
        threat_intel_score=0,
        cve_score=0,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_soc_iq.db"


@pytest.fixture()
def repository(db_path):
    connection = DatabaseConnection(database_path=db_path)
    repo = InvestigationRepository(database=connection)
    yield repo
    connection.close()


# ==========================================================
# DatabaseConnection
# ==========================================================


def test_connect_creates_database_file(db_path):
    connection = DatabaseConnection(database_path=db_path)

    assert not db_path.exists()

    connection.connect()

    assert db_path.exists()
    connection.close()


def test_connect_reuses_same_connection_object(db_path):
    connection = DatabaseConnection(database_path=db_path)

    first = connection.connect()
    second = connection.connect()

    assert first is second
    connection.close()


def test_close_allows_reconnect(db_path):
    connection = DatabaseConnection(database_path=db_path)

    first = connection.connect()
    connection.close()
    second = connection.connect()

    # After close(), a brand new sqlite3.Connection must be handed
    # out rather than reusing the closed one.
    assert first is not second
    connection.close()


def test_close_without_ever_connecting_is_safe(db_path):
    connection = DatabaseConnection(database_path=db_path)

    # Should not raise even though connect() was never called.
    connection.close()


def test_context_manager_closes_connection(db_path):
    connection = DatabaseConnection(database_path=db_path)

    with connection as conn:
        conn.execute("CREATE TABLE t (id INTEGER);")
        conn.commit()

    assert connection._connection is None


def test_connection_row_factory_is_sqlite_row(db_path):
    connection = DatabaseConnection(database_path=db_path)

    conn = connection.connect()

    assert conn.row_factory is sqlite3.Row
    connection.close()


def test_connection_creates_parent_directory(tmp_path):
    nested_path = tmp_path / "nested" / "dir" / "db.sqlite3"
    connection = DatabaseConnection(database_path=nested_path)

    connection.connect()

    assert nested_path.parent.exists()
    connection.close()


def test_failed_initialization_does_not_lock_in_broken_connection(
    db_path, monkeypatch
):
    """
    If PRAGMA setup fails during connect(), self._connection must
    remain None so a later connect() call can retry instead of
    forever handing back a half-configured connection.
    """

    connection = DatabaseConnection(database_path=db_path)

    original_connect = sqlite3.connect

    class ExplodingConnection:
        def __init__(self, real_connection):
            self._real = real_connection

        def __getattr__(self, name):
            return getattr(self._real, name)

        def execute(self, sql, *args, **kwargs):
            if "PRAGMA" in sql:
                raise sqlite3.OperationalError("simulated failure")
            return self._real.execute(sql, *args, **kwargs)

    def fake_connect(path):
        real = original_connect(path)
        return ExplodingConnection(real)

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    with pytest.raises(sqlite3.OperationalError):
        connection.connect()

    assert connection._connection is None


# ==========================================================
# InvestigationRepository: CRUD
# ==========================================================


def test_repository_initializes_table(repository):
    assert repository.count() == 0


def test_save_returns_investigation_id(repository):
    investigation = make_investigation()

    investigation_id = repository.save(investigation)

    assert isinstance(investigation_id, int)
    assert investigation_id > 0
    assert investigation.investigation_id == investigation_id


def test_get_by_id_round_trips_all_fields(repository):
    investigation = make_investigation(
        report_name="apt_report.txt",
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={"status": "ok", "hashes": [{"malicious": 5}]},
        risk_score=88,
        severity="CRITICAL",
        confidence=0.9,
        ioc_score=6,
        threat_intel_score=25,
        cve_score=10,
    )

    investigation_id = repository.save(investigation)
    fetched = repository.get_by_id(investigation_id)

    assert fetched is not None
    assert fetched.report_name == "apt_report.txt"
    assert fetched.iocs == {"sha256": ["a" * 64]}
    assert fetched.threat_intelligence == {
        "status": "ok",
        "hashes": [{"malicious": 5}],
    }
    assert fetched.risk_score == 88
    assert fetched.severity == "CRITICAL"
    assert fetched.confidence == 0.9
    assert fetched.ioc_score == 6
    assert fetched.threat_intel_score == 25
    assert fetched.cve_score == 10
    assert fetched.status == "COMPLETED"


def test_get_by_id_returns_none_for_missing_id(repository):
    assert repository.get_by_id(9999) is None


def test_list_all_orders_newest_first(repository):
    first_id = repository.save(make_investigation(report_name="first.txt"))
    second_id = repository.save(make_investigation(report_name="second.txt"))

    results = repository.list_all()

    assert [r.investigation_id for r in results] == [second_id, first_id]


def test_find_by_report_name(repository):
    repository.save(make_investigation(report_name="target.txt"))
    repository.save(make_investigation(report_name="other.txt"))

    results = repository.find_by_report_name("target.txt")

    assert len(results) == 1
    assert results[0].report_name == "target.txt"


def test_find_by_report_name_no_match_returns_empty_list(repository):
    assert repository.find_by_report_name("nope.txt") == []


def test_exists_by_report_name_true_and_false(repository):
    repository.save(make_investigation(report_name="present.txt"))

    assert repository.exists_by_report_name("present.txt") is True
    assert repository.exists_by_report_name("absent.txt") is False


def test_find_by_severity(repository):
    # Distinct report_name per save: investigations.report_name is
    # UNIQUE as of migration 0004 (F2 fix), and this test's default
    # `make_investigation()` report_name is identical across all
    # three calls -- these overrides only avoid colliding with that
    # constraint and do not change what this test asserts.
    repository.save(make_investigation(report_name="low.txt", severity="LOW"))
    repository.save(make_investigation(report_name="critical1.txt", severity="CRITICAL"))
    repository.save(make_investigation(report_name="critical2.txt", severity="CRITICAL"))

    results = repository.find_by_severity("CRITICAL")

    assert len(results) == 2
    assert all(r.severity == "CRITICAL" for r in results)


def test_find_recent_respects_limit(repository):
    for i in range(5):
        repository.save(make_investigation(report_name=f"r{i}.txt"))

    results = repository.find_recent(limit=2)

    assert len(results) == 2
    # Newest first.
    assert results[0].report_name == "r4.txt"
    assert results[1].report_name == "r3.txt"


def test_delete_removes_investigation(repository):
    investigation_id = repository.save(make_investigation())

    deleted = repository.delete(investigation_id)

    assert deleted is True
    assert repository.get_by_id(investigation_id) is None


def test_delete_missing_id_returns_false(repository):
    assert repository.delete(12345) is False


def test_count_reflects_saves_and_deletes(repository):
    # Distinct report_name per save -- see the comment in
    # test_find_by_severity above.
    id1 = repository.save(make_investigation(report_name="count1.txt"))
    repository.save(make_investigation(report_name="count2.txt"))

    assert repository.count() == 2

    repository.delete(id1)

    assert repository.count() == 1


# ==========================================================
# Error handling: malformed / corrupted rows
# ==========================================================


def test_get_by_id_raises_on_corrupted_json(repository, db_path):
    investigation_id = repository.save(make_investigation())

    # Corrupt the stored IOC JSON directly at the SQL level.
    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.execute(
            "UPDATE investigations SET iocs = ? WHERE id = ?;",
            ("{not valid json", investigation_id),
        )
        raw_conn.commit()

    with pytest.raises(json.JSONDecodeError):
        repository.get_by_id(investigation_id)


def test_get_by_id_raises_on_corrupted_timestamp(repository, db_path):
    investigation_id = repository.save(make_investigation())

    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.execute(
            "UPDATE investigations SET analyzed_at = ? WHERE id = ?;",
            ("not-a-timestamp", investigation_id),
        )
        raw_conn.commit()

    with pytest.raises(ValueError):
        repository.get_by_id(investigation_id)


def test_list_all_propagates_corruption_in_any_row(repository, db_path):
    good_id = repository.save(make_investigation(report_name="good.txt"))
    bad_id = repository.save(make_investigation(report_name="bad.txt"))

    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.execute(
            "UPDATE investigations SET threat_intelligence = ? WHERE id = ?;",
            ("{broken", bad_id),
        )
        raw_conn.commit()

    with pytest.raises(json.JSONDecodeError):
        repository.list_all()


# ==========================================================
# InvestigationService (business layer delegation)
# ==========================================================


class FakeRepository:
    """Fake repository used to verify the service layer delegates
    correctly without touching a real database."""

    def __init__(self):
        self.saved = []
        self.deleted_ids = []

    def save(self, investigation):
        self.saved.append(investigation)
        investigation.investigation_id = len(self.saved)
        return investigation.investigation_id

    def get_by_id(self, investigation_id):
        for inv in self.saved:
            if inv.investigation_id == investigation_id:
                return inv
        return None

    def list_all(self):
        return list(self.saved)

    def find_by_report_name(self, report_name):
        return [
            inv for inv in self.saved if inv.report_name == report_name
        ]

    def exists_by_report_name(self, report_name):
        return any(inv.report_name == report_name for inv in self.saved)

    def find_by_severity(self, severity):
        return [inv for inv in self.saved if inv.severity == severity]

    def find_recent(self, limit=10):
        return list(self.saved)[:limit]

    def delete(self, investigation_id):
        before = len(self.saved)
        self.saved = [
            inv
            for inv in self.saved
            if inv.investigation_id != investigation_id
        ]
        deleted = len(self.saved) != before
        if deleted:
            self.deleted_ids.append(investigation_id)
        return deleted

    def count(self):
        return len(self.saved)


def test_service_default_constructs_real_repository():
    service = InvestigationService(repository=FakeRepository())
    assert isinstance(service._repository, FakeRepository)


def test_service_save_delegates_to_repository():
    fake = FakeRepository()
    service = InvestigationService(repository=fake)

    investigation = make_investigation()
    investigation_id = service.save(investigation)

    assert fake.saved == [investigation]
    assert investigation_id == 1


def test_service_get_latest_by_report_name_picks_max_analyzed_at():
    fake = FakeRepository()
    service = InvestigationService(repository=fake)

    older = make_investigation(
        report_name="dup.txt",
        analyzed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    newer = make_investigation(
        report_name="dup.txt",
        analyzed_at=datetime(2024, 6, 1, tzinfo=UTC),
    )

    service.save(older)
    service.save(newer)

    latest = service.get_latest_by_report_name("dup.txt")

    assert latest is newer


def test_service_get_latest_by_report_name_returns_none_when_absent():
    service = InvestigationService(repository=FakeRepository())

    assert service.get_latest_by_report_name("missing.txt") is None


def test_service_investigation_exists_delegates():
    fake = FakeRepository()
    service = InvestigationService(repository=fake)

    service.save(make_investigation(report_name="exists.txt"))

    assert service.investigation_exists("exists.txt") is True
    assert service.investigation_exists("nope.txt") is False


def test_service_delete_delegates():
    fake = FakeRepository()
    service = InvestigationService(repository=fake)

    investigation_id = service.save(make_investigation())

    assert service.delete(investigation_id) is True
    assert fake.deleted_ids == [investigation_id]


def test_service_count_delegates():
    fake = FakeRepository()
    service = InvestigationService(repository=fake)

    service.save(make_investigation())
    service.save(make_investigation())

    assert service.count() == 2


# ==========================================================
# Persistence across separate repository instances (simulates
# reopening the app against the same on-disk database).
# ==========================================================


def test_persistence_survives_repository_recreation(db_path):
    connection1 = DatabaseConnection(database_path=db_path)
    repo1 = InvestigationRepository(database=connection1)
    investigation_id = repo1.save(make_investigation(report_name="persist.txt"))
    connection1.close()

    connection2 = DatabaseConnection(database_path=db_path)
    repo2 = InvestigationRepository(database=connection2)
    fetched = repo2.get_by_id(investigation_id)
    connection2.close()

    assert fetched is not None
    assert fetched.report_name == "persist.txt"


# ==========================================================
# F2 (MAX-21A forensic audit) -- report_name UNIQUE constraint
# and concurrent duplicate investigation creation.
# ==========================================================


def test_report_name_unique_constraint_rejects_raw_duplicate_insert(
    repository, db_path
):
    """The schema itself refuses a second row with the same
    report_name -- proves the constraint from migration 0004 is
    actually present and enforced, independent of any
    application-level handling of the resulting error."""

    repository.save(make_investigation(report_name="dup.txt"))

    with sqlite3.connect(db_path) as raw_conn:
        with pytest.raises(sqlite3.IntegrityError):
            raw_conn.execute(
                "INSERT INTO investigations ("
                "report_name, analyzed_at, status, iocs, "
                "threat_intelligence, risk_score, severity, "
                "confidence, ioc_score, threat_intel_score, "
                "cve_score) VALUES "
                "('dup.txt', '2024-01-01T00:00:00+00:00', "
                "'COMPLETED', '{}', '{}', 0, 'LOW', 0.0, 0, 0, 0);"
            )


def test_save_resolves_report_name_conflict_to_existing_row(repository):
    """`save()` on a report_name that already exists does not raise:
    it resolves to the already-persisted investigation's ID, and does
    not create a second row."""

    first_id = repository.save(make_investigation(report_name="conflict.txt"))

    second_id = repository.save(
        make_investigation(report_name="conflict.txt", risk_score=99)
    )

    assert second_id == first_id
    assert repository.count() == 1


def test_save_resolving_conflict_reports_created_true_on_success(repository):
    investigation = make_investigation(report_name="fresh.txt")

    investigation_id, created = repository.save_resolving_conflict(
        investigation
    )

    assert created is True
    assert investigation_id > 0
    assert investigation.investigation_id == investigation_id


def test_save_resolving_conflict_reports_created_false_on_conflict(repository):
    winner_id = repository.save(make_investigation(report_name="race.txt"))

    loser = make_investigation(report_name="race.txt", risk_score=1)
    loser_id, created = repository.save_resolving_conflict(loser)

    assert created is False
    assert loser_id == winner_id
    assert loser.investigation_id == winner_id
    assert repository.count() == 1


def test_concurrent_identical_investigation_creation_produces_one_row(
    db_path,
):
    """Deterministic regression test for the F2 TOCTOU race: N
    threads, each holding its own repository/connection (mirroring
    N concurrent analyze_report() calls, which each construct their
    own InvestigationRepository), racing to save an investigation for
    the *same* report_name. Before the F2 fix (no database-level
    uniqueness), every thread's INSERT could succeed, producing N
    rows. After the fix, exactly one INSERT wins and every other
    thread resolves to that same row via
    save_resolving_conflict -- so the database can never end up with
    more than one investigation for that report_name, regardless of
    how many callers raced to create it.
    """

    import threading

    thread_count = 8
    results: list[tuple[int, bool]] = []
    setup_errors: list[str] = []
    results_lock = threading.Lock()
    start_barrier = threading.Barrier(thread_count)

    def worker() -> None:
        # Construction runs the migration runner (F-21B4E-01):
        # previously, a thread that hit that TOCTOU race could raise
        # here *before* reaching the barrier below, and because
        # threading.Barrier requires every party to arrive, that
        # stranded every other thread waiting on it forever -- the
        # exact intermittent hang this test is named for. Guard
        # against that failure mode explicitly (independent of
        # whether the migration runner is actually fixed) so a setup
        # failure is reported as a loud, immediate test failure
        # instead of a silent hang: any construction exception aborts
        # the barrier for every other party.
        try:
            connection = DatabaseConnection(database_path=db_path)
            repo = InvestigationRepository(database=connection)
        except Exception as exc:
            with results_lock:
                setup_errors.append(repr(exc))
            start_barrier.abort()
            return

        investigation = make_investigation(report_name="race_concurrent.txt")

        # Every thread reaches the INSERT at (as close to) the same
        # moment as possible, to actually exercise the race rather
        # than have threads trivially serialize on the GIL/OS
        # scheduler far apart in time.
        try:
            start_barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            with results_lock:
                setup_errors.append(
                    "barrier aborted: a peer thread failed during setup"
                )
            connection.close()
            return

        outcome = repo.save_resolving_conflict(investigation)

        with results_lock:
            results.append(outcome)

        connection.close()

    threads = [
        threading.Thread(target=worker) for _ in range(thread_count)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=15)

    assert not any(thread.is_alive() for thread in threads)
    assert setup_errors == []
    assert len(results) == thread_count

    winning_ids = {
        investigation_id
        for investigation_id, created in results
        if created
    }

    # Exactly one thread's INSERT actually created a row ...
    assert len(winning_ids) == 1

    # ... and every thread -- winner and every loser alike -- resolved
    # to that same investigation ID.
    assert {investigation_id for investigation_id, _ in results} == winning_ids

    # Exactly one row was actually persisted for this report_name --
    # the N-investigations-instead-of-1 failure mode F2 described is
    # not reproducible after this fix.
    verify_connection = DatabaseConnection(database_path=db_path)
    verify_repo = InvestigationRepository(database=verify_connection)
    assert (
        len(verify_repo.find_by_report_name("race_concurrent.txt")) == 1
    )
    verify_connection.close()
