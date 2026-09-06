"""
Domain tests for app.timeline.domain (Phase A4-P2-P3, Part 1/6).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.timeline.domain import (
    MAX_METADATA_BYTES,
    MAX_SUMMARY_LENGTH,
    TimelineEvent,
    TimelineEventType,
    TimelineMetadataError,
    TimelineValidationError,
)


def make_event(**overrides) -> TimelineEvent:
    defaults = dict(
        investigation_id=1,
        event_type=TimelineEventType.ANALYSIS_COMPLETED,
        summary="Analysis completed.",
    )
    defaults.update(overrides)
    return TimelineEvent(**defaults)


# ==========================================================
# Valid construction
# ==========================================================


def test_valid_event_has_expected_defaults():
    event = make_event()

    assert event.source == "system"
    assert event.metadata == {}
    assert event.timestamp.tzinfo is not None
    assert len(event.event_id) == 32  # uuid4().hex


def test_event_id_is_unique_across_instances():
    a = make_event()
    b = make_event()

    assert a.event_id != b.event_id


def test_event_accepts_all_vocabulary_members():
    for event_type in TimelineEventType:
        event = make_event(event_type=event_type, summary="x")
        assert event.event_type is event_type
        assert event.semantics  # every member has documented semantics


def test_event_type_accepts_raw_string_value():
    event = make_event(event_type="analysis.completed")
    assert event.event_type is TimelineEventType.ANALYSIS_COMPLETED


def test_explicit_timestamp_and_metadata_are_preserved():
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    event = make_event(timestamp=ts, metadata={"ioc_count": 31})

    assert event.timestamp == ts
    assert event.metadata == {"ioc_count": 31}


# ==========================================================
# Invalid event type
# ==========================================================


def test_invalid_event_type_string_raises():
    with pytest.raises(TimelineValidationError):
        make_event(event_type="malware.executed")


def test_fabricated_security_event_type_is_rejected():
    # Guards the product principle: the timeline is not allowed to
    # assert unsupported security conclusions.
    for fake_type in (
        "attacker.entered_system",
        "persistence.established",
        "lateral_movement.occurred",
    ):
        with pytest.raises(TimelineValidationError):
            make_event(event_type=fake_type)


# ==========================================================
# Invalid timestamp
# ==========================================================


def test_naive_timestamp_raises():
    with pytest.raises(TimelineValidationError):
        make_event(timestamp=datetime(2026, 1, 1))


def test_non_datetime_timestamp_raises():
    with pytest.raises(TimelineValidationError):
        make_event(timestamp="2026-01-01T00:00:00Z")


# ==========================================================
# Missing investigation id / summary
# ==========================================================


def test_missing_investigation_id_type_raises():
    with pytest.raises(TimelineValidationError):
        make_event(investigation_id=None)


def test_non_positive_investigation_id_raises():
    with pytest.raises(TimelineValidationError):
        make_event(investigation_id=0)

    with pytest.raises(TimelineValidationError):
        make_event(investigation_id=-1)


def test_empty_summary_raises():
    with pytest.raises(TimelineValidationError):
        make_event(summary="")

    with pytest.raises(TimelineValidationError):
        make_event(summary="   ")


def test_empty_source_raises():
    with pytest.raises(TimelineValidationError):
        make_event(source="")


def test_oversized_summary_raises():
    with pytest.raises(TimelineValidationError):
        make_event(summary="x" * (MAX_SUMMARY_LENGTH + 1))


def test_summary_at_max_length_is_accepted():
    event = make_event(summary="x" * MAX_SUMMARY_LENGTH)

    assert len(event.summary) == MAX_SUMMARY_LENGTH


# ==========================================================
# Metadata validation
# ==========================================================


def test_valid_metadata_round_trips():
    event = make_event(metadata={"ioc_count": 31, "ok": True, "tags": ["a", "b"]})
    assert event.metadata == {"ioc_count": 31, "ok": True, "tags": ["a", "b"]}


def test_non_dict_metadata_raises():
    with pytest.raises(TimelineMetadataError):
        make_event(metadata=["not", "a", "dict"])


def test_non_json_serializable_metadata_raises():
    class Unserializable:
        pass

    with pytest.raises(TimelineMetadataError):
        make_event(metadata={"obj": Unserializable()})


def test_oversized_metadata_raises():
    huge = {"blob": "x" * (MAX_METADATA_BYTES + 1)}
    with pytest.raises(TimelineMetadataError):
        make_event(metadata=huge)


def test_metadata_at_bound_is_accepted():
    # A small, well under-the-bound payload never trips the limit.
    event = make_event(metadata={"ioc_count": 1})
    assert event.metadata == {"ioc_count": 1}


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "apiKey",
        "access_token",
        "password",
        "db_password",
        "secret",
        "client_secret",
        "private_key",
        "credential",
    ],
)
def test_secret_shaped_metadata_key_raises(key):
    with pytest.raises(TimelineMetadataError):
        make_event(metadata={key: "should-not-be-storable"})


def test_metadata_error_is_a_validation_error():
    # TimelineMetadataError is a TimelineValidationError subclass --
    # a caller that only handles the parent still catches this.
    assert issubclass(TimelineMetadataError, TimelineValidationError)

    with pytest.raises(TimelineValidationError):
        make_event(metadata={"password": "x"})


def test_dumping_full_investigation_object_is_rejected_by_size():
    fake_investigation_dump = {
        "iocs": {"ipv4": [f"1.2.3.{i}" for i in range(500)]},
        "threat_intelligence": {"raw": "x" * 5000},
    }
    with pytest.raises(TimelineMetadataError):
        make_event(metadata=fake_investigation_dump)
