"""
SOC-IQ
System Health Service

Provides runtime health information for the
dashboard and diagnostics.
"""

from __future__ import annotations

import logging
import os
import sqlite3

from app.database.connection import DatabaseConnection
from app.settings.service import SettingsService

logger = logging.getLogger(__name__)


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

            # The status string alone only tells the analyst *that*
            # the database is unreachable, not *why* -- log the
            # actual error so it's diagnosable instead of leaving
            # only "Disconnected" in the UI with no trace anywhere.
            logger.exception(
                "Database health check failed."
            )

            return "Disconnected"

    # --------------------------------------------------
    # VirusTotal
    # --------------------------------------------------

    def _virustotal_status(self) -> str:
        """
        Verify VirusTotal configuration.
        """

        try:

            settings = self._settings_service.load_settings()

        except Exception:

            # Previously an exception here (a corrupt settings
            # file, a permissions error, etc.) propagated straight
            # out of get_status(). Every caller of get_status() --
            # currently the dashboard's system status display --
            # calls it synchronously from a Qt slot, so an
            # unhandled exception here doesn't degrade gracefully
            # to an honest "unavailable" reading; it surfaces as an
            # application-level error. A settings read failure is
            # exactly the kind of "can't determine status" case
            # this service exists to report honestly.
            logger.exception(
                "Failed to load settings while checking "
                "VirusTotal configuration."
            )

            return "Unavailable"

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