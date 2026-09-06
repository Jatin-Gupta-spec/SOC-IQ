"""
Repository layer for the investigation timeline.

Append-only by design (see TimelineRepository docstring below): this
module intentionally does not offer update_event()/delete_event().
Mirrors app.database.repository.InvestigationRepository's connection
and transaction conventions exactly -- a fresh connection per call
via `with self._database as connection:`, explicit `connection.commit()`,
schema-current-before-use via the shared migration runner -- rather
than introducing a second database access pattern.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from app.database.connection import DatabaseConnection
from app.database.migration_runner import run_migrations
from app.exceptions import DatabaseError
from app.logger import logger
from app.timeline.domain import TimelineEvent, TimelineEventType


class TimelineRepository:
    """
    Repository responsible for persisting and retrieving
    TimelineEvent records.

    Append-only design (Part 1 brief S23): a timeline is a history
    of facts that happened, not a mutable record. This repository
    therefore offers only:

      * append(event)                        -- write one new fact
      * list_for_investigation(investigation_id) -- read a
        timeline back, oldest to newest, deterministically

    There is no update or delete method. If a future event needs to
    be corrected, the intended pattern is to append a new,
    corrective event -- never to rewrite history in place. This is
    a documented product principle here, not merely an omission.
    """

    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        self._database = (
            database if database is not None else DatabaseConnection()
        )

        self._initialize_database()

    def _initialize_database(self) -> None:
        """
        Ensure the database schema (including timeline_events, as of
        migration 0003) is current before this repository is used.
        Delegates to the same shared migration runner
        InvestigationRepository uses -- this repository does not own
        or duplicate schema bootstrap.
        """

        run_migrations(
            database_path=self._database.database_path,
        )

    # ------------------------------------------------------------
    # Row <-> domain conversion
    # ------------------------------------------------------------

    def _row_to_event(self, row: sqlite3.Row) -> TimelineEvent:
        try:
            metadata = (
                json.loads(row["metadata"])
                if row["metadata"] is not None
                else {}
            )

            return TimelineEvent(
                event_id=row["event_id"],
                investigation_id=row["investigation_id"],
                event_type=TimelineEventType(row["event_type"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                source=row["source"],
                summary=row["summary"],
                metadata=metadata,
            )

        except (ValueError, TypeError) as exc:
            logger.error(
                "Failed to deserialize timeline event %s "
                "for investigation %s: %s",
                row["event_id"],
                row["investigation_id"],
                exc,
            )

            raise

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def append(self, event: TimelineEvent) -> TimelineEvent:
        """
        Persist a new TimelineEvent.

        `event` is expected to already be a validated TimelineEvent
        (validation happens in TimelineEvent.__post_init__, per the
        Part 1 brief's "the repository must validate or safely rely
        on validated domain objects"). This method additionally
        translates a foreign-key violation (investigation_id does
        not reference an existing investigation) into
        app.exceptions.DatabaseError, the project's existing
        database-error type, rather than letting a raw
        sqlite3.IntegrityError leak past this layer.

        Returns the same event back (for a consistent call-site
        shape with InvestigationRepository.save(), which returns the
        assigned id -- here the id is already assigned by the
        caller/domain layer, so the event itself is returned).
        """

        logger.info(
            "Appending timeline event %s (%s) for investigation %d",
            event.event_id,
            event.event_type.value,
            event.investigation_id,
        )

        with self._database as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO timeline_events (
                        event_id,
                        investigation_id,
                        event_type,
                        timestamp,
                        source,
                        summary,
                        metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.investigation_id,
                        event.event_type.value,
                        event.timestamp.isoformat(),
                        event.source,
                        event.summary,
                        json.dumps(event.metadata) if event.metadata else None,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                logger.error(
                    "Failed to append timeline event %s: %s",
                    event.event_id,
                    exc,
                )

                raise DatabaseError(
                    "Could not append timeline event for "
                    f"investigation {event.investigation_id}: "
                    "the investigation does not exist, or the "
                    "event id is already in use."
                ) from exc

        logger.info(
            "Timeline event %s appended.",
            event.event_id,
        )

        return event

    def list_for_investigation(
        self,
        investigation_id: int,
    ) -> list[TimelineEvent]:
        """
        Return every timeline event for `investigation_id`, ordered
        oldest -> newest, deterministically (ties broken by
        insertion order via SQLite `rowid` -- see migration 0003's
        header for why timestamp alone is not a sufficient sole
        ordering key).

        Returns an empty list for an investigation with no timeline
        events (including one that does not exist -- this method
        does not itself verify the investigation exists; a
        nonexistent id simply yields no rows, matching this table's
        own foreign-key semantics rather than adding a second,
        separate existence check).
        """

        with self._database as connection:
            cursor = connection.execute(
                """
                SELECT
                    event_id,
                    investigation_id,
                    event_type,
                    timestamp,
                    source,
                    summary,
                    metadata
                FROM timeline_events
                WHERE investigation_id = ?
                ORDER BY timestamp ASC, rowid ASC;
                """,
                (investigation_id,),
            )

            rows = cursor.fetchall()

        return [self._row_to_event(row) for row in rows]
