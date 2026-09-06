"""
Repository layer for SOC-IQ investigations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.database.connection import DatabaseConnection
from app.database.migration_runner import run_migrations
from app.database.models import Investigation
from app.logger import logger


class InvestigationRepository:
    """
    Repository responsible for persisting
    Investigation objects.
    """

    def __init__(
        self,
        database: DatabaseConnection | None = None,
    ) -> None:
        """
        Initialize the repository.
        """

        self._database = (
            database
            if database is not None
            else DatabaseConnection()
        )

        self._initialize_database()

    def _row_to_investigation(
        self,
        row: tuple,
    ) -> Investigation:
        """
        Convert a raw database row into an
        Investigation instance.

        Deserialization failures (malformed JSON,
        unparsable timestamps, etc.) are logged with
        the offending investigation ID and then
        re-raised. They are never swallowed into a
        default/empty Investigation, since that would
        silently misrepresent corrupted data as a
        valid one.
        """

        investigation_id = row[0]

        try:

            return Investigation(
                investigation_id=investigation_id,
                report_name=row[1],
                analyzed_at=datetime.fromisoformat(
                    row[2],
                ),
                status=row[3],
                iocs=json.loads(
                    row[4],
                ),
                threat_intelligence=json.loads(
                    row[5],
                ),
                risk_score=row[6],
                severity=row[7],
                confidence=row[8],
                ioc_score=row[9],
                threat_intel_score=row[10],
                cve_score=row[11],
                # A4-P1: NULL on a pre-provenance ("legacy") row is
                # loaded as `None`, exactly the same honest "never
                # calculated" state `Investigation.source_sha256`'s
                # own docstring describes -- not backfilled, not
                # coerced to a placeholder string/0.
                source_sha256=row[12],
                source_size_bytes=row[13],
            )

        except (
            ValueError,
            TypeError,
        ) as exc:

            logger.error(
                "Failed to deserialize investigation "
                "ID %s from database row: %s",
                investigation_id,
                exc,
            )

            raise

    def _initialize_database(self) -> None:
        """
        Ensure the database schema is at the current version.

        Schema creation and evolution is owned by the migration
        runner (see app.database.migration_runner), not by this
        repository. This method's only responsibility is to invoke
        that runner -- against this repository's configured database
        path -- before any other method touches the database, so a
        fresh database is bootstrapped and an existing one is brought
        up to date (or left untouched if already current).
        """

        logger.info(
            "Ensuring investigation database schema is current."
        )

        run_migrations(
            database_path=self._database.database_path,
        )

        logger.info(
            "Database schema check completed."
        )

    def save(
        self,
        investigation: Investigation,
    ) -> int:
        """
        Save an investigation.

        F2 (MAX-21A forensic audit) hardening: `investigations
        .report_name` is now protected by a database-level UNIQUE
        constraint (see migration 0004_unique_report_name.sql). If
        this INSERT loses a race against a concurrent insert of the
        same `report_name` -- the exact TOCTOU window
        `app.analyzer.analyze_report`'s prior
        exists_by_report_name()-then-save() sequence could not close
        on its own -- SQLite raises `sqlite3.IntegrityError` here
        instead of allowing a second row to be created. That
        conflict is not surfaced to the caller as a crash: it is
        resolved to the investigation that won the race (see
        `save_resolving_conflict`, which this method delegates to),
        and this row's `investigation_id` is set to that winner's ID.

        This keeps `save()`'s existing `-> int` contract for every
        pre-existing caller (including every test in
        tests/test_database.py that asserts on its return value) --
        callers that need to distinguish "this row was newly created"
        from "this row lost a uniqueness race and was resolved to an
        existing one" should use `save_resolving_conflict` directly
        (see `app.analyzer.analyze_report`, which does).
        """

        investigation_id, _created = (
            self.save_resolving_conflict(
                investigation,
            )
        )

        return investigation_id

    def save_resolving_conflict(
        self,
        investigation: Investigation,
    ) -> tuple[int, bool]:
        """
        Save an investigation, resolving a `report_name` uniqueness
        conflict instead of raising it.

        Returns:
            A `(investigation_id, created)` tuple:

            * `created is True`: this call's INSERT succeeded and
              `investigation_id` is the newly created row's ID.
            * `created is False`: this call's INSERT lost a
              concurrent race against another writer inserting the
              same `report_name` (or -- far less likely, since the
              constraint did not exist before migration 0004 -- an
              identically-named row already existed from before this
              fix). `investigation_id` is the ID of the
              already-persisted row for that `report_name`, resolved
              by re-querying `find_by_report_name` from *inside* the
              `except` block, i.e. after the conflict, so it reflects
              whichever row the database actually committed --
              never a value guessed or cached from before the
              conflict was observed.

        In both cases `investigation.investigation_id` is set to the
        returned ID on this in-memory object, mirroring `save()`'s
        existing behavior.
        """

        logger.info(
            "Saving investigation: %s",
            investigation.report_name,
        )

        try:

            with self._database as connection:

                cursor = connection.execute(
                    """
                    INSERT INTO investigations (
                        report_name,
                        analyzed_at,
                        status,
                        iocs,
                        threat_intelligence,
                        risk_score,
                        severity,
                        confidence,
                        ioc_score,
                        threat_intel_score,
                        cve_score,
                        source_sha256,
                        source_size_bytes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        investigation.report_name,
                        investigation.analyzed_at.isoformat(),
                        investigation.status,
                        json.dumps(
                            investigation.iocs,
                        ),
                        json.dumps(
                            investigation.threat_intelligence,
                        ),
                        investigation.risk_score,
                        investigation.severity,
                        investigation.confidence,
                        investigation.ioc_score,
                        investigation.threat_intel_score,
                        investigation.cve_score,
                        investigation.source_sha256,
                        investigation.source_size_bytes,
                    ),
                )

                connection.commit()

                investigation_id = cursor.lastrowid

        except sqlite3.IntegrityError as exc:

            logger.warning(
                "Investigation insert for report '%s' hit the "
                "report_name UNIQUE constraint (F2 race resolution); "
                "resolving to the already-persisted investigation "
                "instead of failing. (%s)",
                investigation.report_name,
                exc,
            )

            existing_matches = self.find_by_report_name(
                investigation.report_name,
            )

            if not existing_matches:

                # The constraint fired but a fresh lookup finds no
                # row for this report_name at all. That combination
                # should be unreachable -- it would mean the
                # conflicting row was deleted between the failed
                # INSERT and this SELECT -- so this is surfaced as a
                # hard failure rather than silently fabricating a
                # result.
                raise RuntimeError(
                    "Investigation save for report "
                    f"'{investigation.report_name}' hit a "
                    "uniqueness conflict, but no existing "
                    "investigation could be found to resolve it to."
                ) from exc

            # `find_by_report_name` orders newest-first (see its
            # docstring), so the winner of the race is the first
            # element -- the same "latest match wins" semantics
            # `app.analyzer.analyze_report`'s pre-existing duplicate
            # handling already relies on.
            winner = existing_matches[0]

            investigation.investigation_id = (
                winner.investigation_id
            )

            logger.info(
                "Resolved investigation save for report '%s' to "
                "existing investigation ID %s.",
                investigation.report_name,
                winner.investigation_id,
            )

            return winner.investigation_id, False

        if investigation_id is None:

            raise ValueError(
                "Failed to retrieve investigation ID."
            )

        investigation.investigation_id = (
            investigation_id
        )

        logger.info(
            "Investigation saved with ID %d",
            investigation_id,
        )

        return investigation_id, True

    def get_by_id(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Retrieve an investigation by ID.
        """

        logger.info(
            "Fetching investigation ID %d",
            investigation_id,
        )

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT
                    id,
                    report_name,
                    analyzed_at,
                    status,
                    iocs,
                    threat_intelligence,
                    risk_score,
                    severity,
                    confidence,
                    ioc_score,
                    threat_intel_score,
                    cve_score,
                    source_sha256,
                    source_size_bytes
                FROM investigations
                WHERE id = ?;
                """,
                (
                    investigation_id,
                ),
            )

            row = cursor.fetchone()

        if row is None:

            logger.warning(
                "Investigation ID %d not found.",
                investigation_id,
            )

            return None

        return self._row_to_investigation(row)

    def list_all(
        self,
    ) -> list[Investigation]:
        """
        Return all investigations ordered by
        newest first.
        """

        logger.info(
            "Loading all investigations."
        )

        investigations: list[
            Investigation
        ] = []

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT
                    id,
                    report_name,
                    analyzed_at,
                    status,
                    iocs,
                    threat_intelligence,
                    risk_score,
                    severity,
                    confidence,
                    ioc_score,
                    threat_intel_score,
                    cve_score,
                    source_sha256,
                    source_size_bytes
                FROM investigations
                ORDER BY id DESC;
                """
            )

            rows = cursor.fetchall()

        for row in rows:

            investigations.append(
                self._row_to_investigation(row)
            )

        logger.info(
            "Loaded %d investigation(s).",
            len(investigations),
        )

        return investigations

    def find_by_report_name(
        self,
        report_name: str,
    ) -> list[Investigation]:
        """
        Find investigations by report name.

        Results are ordered by newest first.
        """

        logger.info(
            "Searching investigations by report name: %s",
            report_name,
        )

        investigations: list[Investigation] = []

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT
                    id,
                    report_name,
                    analyzed_at,
                    status,
                    iocs,
                    threat_intelligence,
                    risk_score,
                    severity,
                    confidence,
                    ioc_score,
                    threat_intel_score,
                    cve_score,
                    source_sha256,
                    source_size_bytes
                FROM investigations
                WHERE report_name = ?
                ORDER BY id DESC;
                """,
                (
                    report_name,
                ),
            )

            rows = cursor.fetchall()

        for row in rows:

            investigations.append(
                self._row_to_investigation(row)
            )
        logger.info(
            "Found %d investigation(s) for report '%s'.",
            len(investigations),
            report_name,
        )

        return investigations

    def exists_by_report_name(
        self,
        report_name: str,
    ) -> bool:
        """
        Determine whether an investigation already
        exists for the specified report name.

        Args:
            report_name:
                Name of the analyzed report.

        Returns:
            True if an investigation exists,
            otherwise False.
        """

        logger.info(
            "Checking whether report '%s' already exists.",
            report_name,
        )

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM investigations
                    WHERE report_name = ?
                );
                """,
                (
                    report_name,
                ),
            )

            row = cursor.fetchone()

        exists = (
            bool(row[0])
            if row is not None
            else False
        )

        logger.info(
            "Duplicate investigation exists: %s",
            exists,
        )

        return exists

    def find_by_severity(
        self,
        severity: str,
    ) -> list[Investigation]:
        """
        Find investigations by severity.

        Results are ordered by newest first.
        """

        logger.info(
            "Searching investigations by severity: %s",
            severity,
        )

        investigations: list[
            Investigation
        ] = []

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT
                    id,
                    report_name,
                    analyzed_at,
                    status,
                    iocs,
                    threat_intelligence,
                    risk_score,
                    severity,
                    confidence,
                    ioc_score,
                    threat_intel_score,
                    cve_score,
                    source_sha256,
                    source_size_bytes
                FROM investigations
                WHERE severity = ?
                ORDER BY id DESC;
                """,
                (
                    severity,
                ),
            )

            rows = cursor.fetchall()

        for row in rows:

            investigations.append(
                self._row_to_investigation(row)
            )

        logger.info(
            "Found %d investigation(s) with severity '%s'.",
            len(investigations),
            severity,
        )

        return investigations

    def find_recent(
        self,
        limit: int = 10,
    ) -> list[Investigation]:
        """
        Return the most recent investigations.

        Results are ordered by newest first.
        """

        logger.info(
            "Loading %d most recent investigation(s).",
            limit,
        )

        investigations: list[
            Investigation
        ] = []

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT
                    id,
                    report_name,
                    analyzed_at,
                    status,
                    iocs,
                    threat_intelligence,
                    risk_score,
                    severity,
                    confidence,
                    ioc_score,
                    threat_intel_score,
                    cve_score,
                    source_sha256,
                    source_size_bytes
                FROM investigations
                ORDER BY id DESC
                LIMIT ?;
                """,
                (
                    limit,
                ),
            )

            rows = cursor.fetchall()

        for row in rows:

            investigations.append(
                self._row_to_investigation(row)
            )

        logger.info(
            "Loaded %d recent investigation(s).",
            len(investigations),
        )

        return investigations

    def delete(
        self,
        investigation_id: int,
    ) -> bool:
        """
        Delete an investigation by ID.

        Returns:
            True if an investigation was deleted,
            otherwise False.
        """

        logger.info(
            "Deleting investigation ID %d",
            investigation_id,
        )

        with self._database as connection:

            cursor = connection.execute(
                """
                DELETE FROM investigations
                WHERE id = ?;
                """,
                (
                    investigation_id,
                ),
            )

            connection.commit()

        deleted = cursor.rowcount > 0

        if deleted:

            logger.info(
                "Investigation ID %d deleted.",
                investigation_id,
            )

        else:

            logger.warning(
                "Investigation ID %d not found.",
                investigation_id,
            )

        return deleted

    def count(
        self,
    ) -> int:
        """
        Return the total number of
        investigations.
        """

        logger.info(
            "Counting investigations."
        )

        with self._database as connection:

            cursor = connection.execute(
                """
                SELECT COUNT(*)
                FROM investigations;
                """
            )

            total = cursor.fetchone()[0]

        logger.info(
            "Total investigations: %d",
            total,
        )

        return total
