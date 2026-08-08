"""
Service layer for SOC-IQ investigations.

This module provides the business layer for
creating, saving, and retrieving investigations.
"""

from __future__ import annotations

from datetime import datetime

from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.logger import logger


class InvestigationService:
    """
    Business layer for investigation
    persistence and retrieval.

    This layer isolates the application
    from the repository implementation and
    is the correct place for future
    business rules.
    """

    def __init__(
        self,
        repository: InvestigationRepository | None = None,
    ) -> None:
        """
        Initialize the investigation service.
        """

        self._repository = (
            repository
            if repository is not None
            else InvestigationRepository()
        )

        logger.debug(
            "InvestigationService initialized."
        )

    def save(
        self,
        investigation: Investigation,
    ) -> int:
        """
        Save an investigation.

        Returns:
            Database investigation ID.
        """

        logger.info(
            "Saving investigation."
        )

        return self._repository.save(
            investigation,
        )

    def get_by_id(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Retrieve an investigation by ID.
        """

        logger.info(
            "Loading investigation %d",
            investigation_id,
        )

        return self._repository.get_by_id(
            investigation_id,
        )

    def list_all(
        self,
    ) -> list[Investigation]:
        """
        Return all investigations.
        """

        logger.info(
            "Loading investigation history."
        )

        return self._repository.list_all()

    def find_by_report_name(
        self,
        report_name: str,
    ) -> list[Investigation]:
        """
        Find investigations by report name.
        """

        logger.info(
            "Finding investigations for report '%s'.",
            report_name,
        )

        return self._repository.find_by_report_name(
            report_name,
        )

    def investigation_exists(
        self,
        report_name: str,
    ) -> bool:
        """
        Determine whether an investigation
        already exists for the specified report.
        """

        logger.info(
            "Checking whether report '%s' already exists.",
            report_name,
        )

        return self._repository.exists_by_report_name(
            report_name,
        )

    def get_latest_by_report_name(
        self,
        report_name: str,
    ) -> Investigation | None:
        """
        Return the newest investigation for
        the specified report.
        """

        logger.info(
            "Loading latest investigation for '%s'.",
            report_name,
        )

        investigations = (
            self._repository.find_by_report_name(
                report_name,
            )
        )

        if not investigations:
            return None

        # "Latest" is determined explicitly here rather
        # than by trusting the repository to return rows
        # in a particular order. `find_by_report_name`
        # documents no ordering guarantee, so silently
        # relying on `investigations[0]` meant a future
        # change to the repository's query (e.g. an added
        # ORDER BY, a switch to a different storage engine)
        # could make this method start returning the wrong
        # investigation with no visible error.
        return max(
            investigations,
            key=lambda investigation: (
                investigation.analyzed_at
                or datetime.min
            ),
        )

    def find_by_severity(
        self,
        severity: str,
    ) -> list[Investigation]:
        """
        Find investigations by severity.
        """

        logger.info(
            "Finding investigations with severity '%s'.",
            severity,
        )

        return self._repository.find_by_severity(
            severity,
        )

    def find_recent(
        self,
        limit: int = 10,
    ) -> list[Investigation]:
        """
        Return the most recent investigations.
        """

        logger.info(
            "Loading %d recent investigations.",
            limit,
        )

        return self._repository.find_recent(
            limit,
        )

    def delete(
        self,
        investigation_id: int,
    ) -> bool:
        """
        Delete an investigation.

        Returns:
            True if deleted,
            otherwise False.
        """

        logger.info(
            "Deleting investigation %d",
            investigation_id,
        )

        return self._repository.delete(
            investigation_id,
        )

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

        return self._repository.count()
