"""
SOC-IQ
System Health Service

Provides runtime health information for the
dashboard and diagnostics.
"""

from __future__ import annotations

import os
import sqlite3

from app.database.connection import DatabaseConnection


class SystemHealthService:
    """
    Provides runtime system health.
    """

    def __init__(self) -> None:

        self._database = DatabaseConnection()

    # --------------------------------------------------
    # Database
    # --------------------------------------------------

    def _database_status(self) -> str:
        """
        Verify database connectivity.
        """

        try:

            with self._database as connection:

                connection.execute(
                    "SELECT 1;"
                )

            return "Connected"

        except sqlite3.Error:

            return "Disconnected"

    # --------------------------------------------------
    # VirusTotal
    # --------------------------------------------------

    def _virustotal_status(self) -> str:
        """
        Verify VirusTotal configuration.
        """

        api_key = os.getenv(
            "VIRUSTOTAL_API_KEY",
            "",
        ).strip()

        if api_key:

            return "Configured"

        return "API Key Missing"

    # --------------------------------------------------
    # Repository
    # --------------------------------------------------

    def _repository_status(self) -> str:
        """
        Repository layer status.
        """

        return "Operational"

    # --------------------------------------------------
    # Analysis Engine
    # --------------------------------------------------

    def _analysis_engine_status(self) -> str:
        """
        Analysis engine status.
        """

        return "Ready"

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def get_status(
        self,
    ) -> dict[str, str]:
        """
        Return overall system health.
        """

        return {

            "database": self._database_status(),

            "repository": self._repository_status(),

            "analysis_engine": (
                self._analysis_engine_status()
            ),

            "virustotal": (
                self._virustotal_status()
            ),
        }