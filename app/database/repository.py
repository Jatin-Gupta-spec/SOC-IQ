"""
Repository layer for SOC-IQ investigations.
"""

from __future__ import annotations

import json
from datetime import datetime

from app.database.connection import DatabaseConnection
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
        Create required database tables.
        """

        logger.info(
            "Initializing investigation database."
        )

        with self._database as connection:

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

        logger.info(
            "Database initialization completed."
        )

    def save(
        self,
        investigation: Investigation,
    ) -> int:
        """
        Save an investigation.
        """

        logger.info(
            "Saving investigation: %s",
            investigation.report_name,
        )

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
                    cve_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
                ),
            )

            connection.commit()

            investigation_id = cursor.lastrowid

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

        return investigation_id

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
                    cve_score
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
                    cve_score
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
                    cve_score
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
                    cve_score
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
                    cve_score
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
