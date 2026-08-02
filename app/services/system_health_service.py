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
from app.settings.service import SettingsService


class SystemHealthService:
    """
    Provides runtime system health.
    """

    def __init__(self) -> None:

        self._database = DatabaseConnection()
        self._settings_service = SettingsService()

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

        settings = self._settings_service.load_settings()

        if settings.virustotal_api_key.strip():

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