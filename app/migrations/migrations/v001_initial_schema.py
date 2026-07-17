"""
Initial database schema migration.

Creates the investigation table used by SOC-IQ.
"""

from __future__ import annotations

from sqlite3 import Connection

from app.migrations.migration import Migration


class InitialSchemaMigration(Migration):
    """
    Creates the initial SOC-IQ database schema.
    """

    version = 1

    description = "Create investigations table."

    def upgrade(
        self,
        connection: Connection,
    ) -> None:
        """
        Create the initial investigation table.
        """

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
                severity TEXT NOT NULL
            );
            """
        )

        connection.commit()