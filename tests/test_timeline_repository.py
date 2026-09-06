"""
Repository tests for app.timeline.repository.TimelineRepository
(Phase A4-P2-P3, Part 1/6).
"""

from __future__ import annotations

import json

import pytest

from app.database.connection import DatabaseConnection
from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.exceptions import DatabaseError
from app.timeline.domain import TimelineEvent, TimelineEventType
from app.timeline.repository import TimelineRepository


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
    return tmp_path / "timeline_repo_test.db"


@pytest.fixture()
def connection(db_path):
    conn = DatabaseConnection(database_path=db_path)
    yield conn
    conn.close()


@pytest.fixture()
def investigation_repo(connection):
    return InvestigationRepository(database=connection)


@pytest.fixture()
def timeline_repo(connection):
    return TimelineRepository(database=connection)


def test_append_and_retrieve_single_event(investigation_repo, timeline_repo):
    inv_id = investigation_repo.save(make_investigation())

    event = TimelineEvent(
        investigation_id=inv_id,
        event_type=TimelineEventType.INVESTIGATION_CREATED,
        summary="Investigation created.",
    )
    timeline_repo.append(event)

    events = timeline_repo.list_for_investigation(inv_id)
    assert len(events) == 1
    assert events[0].event_id == event.event_id
    assert events[0].event_type == TimelineEventType.INVESTIGATION_CREATED


def test_empty_timeline_for_investigation_with_no_events(
    investigation_repo, timeline_repo
):
    inv_id = investigation_repo.save(make_investigation())
    assert timeline_repo.list_for_investigation(inv_id) == []


def test_empty_timeline_for_nonexistent_investigation(timeline_repo):
    assert timeline_repo.list_for_investigation(999999) == []


def test_ordering_is_oldest_to_newest(investigation_repo, timeline_repo):
    from datetime import UTC, datetime, timedelta

    inv_id = investigation_repo.save(make_investigation())
    base = datetime(2026, 1, 1, tzinfo=UTC)

    for i, event_type in enumerate(
        [
            TimelineEventType.INVESTIGATION_CREATED,
            TimelineEventType.ANALYSIS_STARTED,
            TimelineEventType.ANALYSIS_COMPLETED,
        ]
    ):
        timeline_repo.append(
            TimelineEvent(
                investigation_id=inv_id,
                event_type=event_type,
                summary=f"step {i}",
                timestamp=base + timedelta(minutes=i),
            )
        )

    events = timeline_repo.list_for_investigation(inv_id)
    assert [e.event_type for e in events] == [
        TimelineEventType.INVESTIGATION_CREATED,
        TimelineEventType.ANALYSIS_STARTED,
        TimelineEventType.ANALYSIS_COMPLETED,
    ]


def test_equal_timestamps_preserve_append_order(investigation_repo, timeline_repo):
    from datetime import UTC, datetime

    inv_id = investigation_repo.save(make_investigation())
    same_ts = datetime(2026, 1, 1, tzinfo=UTC)

    for summary in ("first", "second", "third"):
        timeline_repo.append(
            TimelineEvent(
                investigation_id=inv_id,
                event_type=TimelineEventType.ANALYSIS_STARTED,
                summary=summary,
                timestamp=same_ts,
            )
        )

    events = timeline_repo.list_for_investigation(inv_id)
    assert [e.summary for e in events] == ["first", "second", "third"]


def test_multiple_investigations_do_not_leak_events(
    investigation_repo, timeline_repo
):
    inv_a = investigation_repo.save(make_investigation(report_name="a.txt"))
    inv_b = investigation_repo.save(make_investigation(report_name="b.txt"))

    timeline_repo.append(
        TimelineEvent(
            investigation_id=inv_a,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="a created",
        )
    )
    timeline_repo.append(
        TimelineEvent(
            investigation_id=inv_b,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="b created",
        )
    )

    events_a = timeline_repo.list_for_investigation(inv_a)
    events_b = timeline_repo.list_for_investigation(inv_b)

    assert len(events_a) == 1 and events_a[0].summary == "a created"
    assert len(events_b) == 1 and events_b[0].summary == "b created"

    # Investigation A's timeline must never contain B's events, and
    # vice versa.
    assert all(e.investigation_id == inv_a for e in events_a)
    assert all(e.investigation_id == inv_b for e in events_b)


def test_append_to_nonexistent_investigation_raises_database_error(
    timeline_repo,
):
    event = TimelineEvent(
        investigation_id=999999,
        event_type=TimelineEventType.REPORT_IMPORTED,
        summary="orphan",
    )

    with pytest.raises(DatabaseError):
        timeline_repo.append(event)


def test_database_persistence_across_repository_instances(
    db_path, investigation_repo
):
    inv_id = investigation_repo.save(make_investigation())

    conn1 = DatabaseConnection(database_path=db_path)
    repo1 = TimelineRepository(database=conn1)
    repo1.append(
        TimelineEvent(
            investigation_id=inv_id,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="created",
        )
    )
    conn1.close()

    conn2 = DatabaseConnection(database_path=db_path)
    repo2 = TimelineRepository(database=conn2)
    events = repo2.list_for_investigation(inv_id)
    conn2.close()

    assert len(events) == 1
    assert events[0].summary == "created"


def test_timeline_deleted_when_investigation_deleted(
    investigation_repo, timeline_repo
):
    inv_id = investigation_repo.save(make_investigation())
    timeline_repo.append(
        TimelineEvent(
            investigation_id=inv_id,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="created",
        )
    )
    assert len(timeline_repo.list_for_investigation(inv_id)) == 1

    investigation_repo.delete(inv_id)

    assert timeline_repo.list_for_investigation(inv_id) == []


# ==========================================================
# Part 2: identity collisions, corrupted rows, scale
# ==========================================================


def test_append_duplicate_event_id_raises_database_error(
    investigation_repo, timeline_repo
):
    inv_id = investigation_repo.save(make_investigation())

    event = TimelineEvent(
        investigation_id=inv_id,
        event_type=TimelineEventType.INVESTIGATION_CREATED,
        summary="first",
    )
    timeline_repo.append(event)

    # Same event_id, different content -- event_id is the PRIMARY
    # KEY, so this must fail rather than silently overwrite or
    # duplicate the historical record.
    duplicate = TimelineEvent(
        event_id=event.event_id,
        investigation_id=inv_id,
        event_type=TimelineEventType.ANALYSIS_STARTED,
        summary="second",
    )

    with pytest.raises(DatabaseError):
        timeline_repo.append(duplicate)

    # The original row must be unaffected by the rejected duplicate.
    events = timeline_repo.list_for_investigation(inv_id)
    assert len(events) == 1
    assert events[0].summary == "first"


def test_list_for_investigation_raises_on_corrupted_metadata_json(
    investigation_repo, timeline_repo, db_path
):
    import sqlite3

    inv_id = investigation_repo.save(make_investigation())
    timeline_repo.append(
        TimelineEvent(
            investigation_id=inv_id,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="created",
        )
    )

    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.execute(
            "UPDATE timeline_events SET metadata = ? "
            "WHERE investigation_id = ?;",
            ("{not valid json", inv_id),
        )
        raw_conn.commit()

    # Corrupted metadata is never silently coerced into an empty
    # dict or dropped -- it must fail loudly, same as
    # InvestigationRepository's own corrupted-JSON handling
    # (see tests/test_database.py::test_get_by_id_raises_on_corrupted_json).
    with pytest.raises(json.JSONDecodeError):
        timeline_repo.list_for_investigation(inv_id)


def test_list_for_investigation_raises_on_corrupted_timestamp(
    investigation_repo, timeline_repo, db_path
):
    import sqlite3

    inv_id = investigation_repo.save(make_investigation())
    timeline_repo.append(
        TimelineEvent(
            investigation_id=inv_id,
            event_type=TimelineEventType.INVESTIGATION_CREATED,
            summary="created",
        )
    )

    with sqlite3.connect(db_path) as raw_conn:
        raw_conn.execute(
            "UPDATE timeline_events SET timestamp = ? "
            "WHERE investigation_id = ?;",
            ("not-a-timestamp", inv_id),
        )
        raw_conn.commit()

    with pytest.raises(ValueError):
        timeline_repo.list_for_investigation(inv_id)


def test_large_timeline_round_trips_in_order(investigation_repo, timeline_repo):
    from datetime import UTC, datetime, timedelta

    inv_id = investigation_repo.save(make_investigation())
    base = datetime(2026, 1, 1, tzinfo=UTC)
    event_types = list(TimelineEventType)

    for i in range(200):
        timeline_repo.append(
            TimelineEvent(
                investigation_id=inv_id,
                event_type=event_types[i % len(event_types)],
                summary=f"event {i}",
                timestamp=base + timedelta(seconds=i),
            )
        )

    events = timeline_repo.list_for_investigation(inv_id)
    assert len(events) == 200
    assert [e.summary for e in events] == [f"event {i}" for i in range(200)]
    # No cross-contamination from this scale of insert.
    assert all(e.investigation_id == inv_id for e in events)
