"""
History controller for the SOC-IQ desktop application.

This controller prepares investigation history data
for presentation in the GUI and delegates business
operations to the InvestigationService.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService


class HistoryController:
    """
    Controller responsible for retrieving and
    managing investigation history.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
    ) -> None:
        """
        Initialize the history controller.
        """

        self._investigation_service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )

    def get_recent_investigations(
        self,
        limit: int = 10,
    ) -> list[Investigation]:
        """
        Return recent investigations.
        """

        return self._investigation_service.find_recent(
            limit,
        )

    def search_by_report_name(
        self,
        report_name: str,
    ) -> list[Investigation]:
        """
        Search investigations by report name.
        """

        return (
            self._investigation_service.find_by_report_name(
                report_name,
            )
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
            True if the investigation was deleted,
            otherwise False.
        """

        return self._investigation_service.delete(
            investigation_id,
        )

    def get_investigation(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Retrieve a single investigation by ID.
        """

        return self._investigation_service.get_by_id(
            investigation_id,
        )

    def get_total_investigations(
        self,
    ) -> int:
        """
        Return the total number of investigations.
        """

        return self._investigation_service.count()