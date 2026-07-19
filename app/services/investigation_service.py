
"""
Service layer for SOC-IQ investigations.

This module provides the business layer for creating, retrieving,
listing, searching, deleting, and counting investigations.

The service layer isolates the GUI and controllers from the
repository implementation. Business rules should always be added
here instead of directly inside controllers.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.repository import InvestigationRepository
from app.logger import logger


class InvestigationService:
    """
    Business layer for investigation persistence and retrieval.

    This service coordinates investigation operations and delegates
    persistence to the repository layer.
    """

    def __init__(
        self,
        repository: InvestigationRepository | None = None,
    ) -> None:
        """
        Initialize the investigation service.

        Args:
            repository:
                Optional repository instance used for dependency
                injection during testing.
        """

        self._repository = (
            repository
            if repository is not None
            else InvestigationRepository()
        )

    def save_investigation(
        self,
        investigation: Investigation,
    ) -> int:
        """
        Save an investigation.

        Args:
            investigation:
                Investigation to persist.

        Returns:
            Database ID of the saved investigation.
        """

        logger.info(
            "Saving investigation through service layer."
        )

        return self._repository.save(
            investigation,
        )

    def get_investigation(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Retrieve an investigation by ID.
        """

        logger.info(
            "Loading investigation ID %d.",
            investigation_id,
        )

        return self._repository.get_by_id(
            investigation_id,
        )

    def list_investigations(
        self,
    ) -> list[Investigation]:
        """
        Return all investigations.
        """

        logger.info(
            "Listing investigations."
        )

        return self._repository.list_all()

    def find_by_report_name(
        self,
        report_name: str,
    ) -> list[Investigation]:
        """
        Search investigations by report name.
        """

        logger.info(
            "Searching investigations by report name."
        )

        return self._repository.find_by_report_name(
            report_name,
        )

    def find_by_severity(
        self,
        severity: str,
    ) -> list[Investigation]:
        """
        Search investigations by severity.
        """

        logger.info(
            "Searching investigations by severity."
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
            "Loading recent investigations."
        )

        return self._repository.find_recent(
            limit,
        )

    def delete_investigation(
        self,
        investigation_id: int,
    ) -> bool:
        """
        Delete an investigation.

        Args:
            investigation_id:
                Database ID of the investigation.

        Returns:
            True if deleted successfully,
            otherwise False.
        """

        logger.info(
            "Deleting investigation ID %d.",
            investigation_id,
        )

        return self._repository.delete(
            investigation_id,
        )

    def count_investigations(
        self,
    ) -> int:
        """
        Return the total number of investigations.
        """

        logger.info(
            "Counting investigations."
        )

        return self._repository.count()

