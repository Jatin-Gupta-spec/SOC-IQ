"""
History controller for the SOC-IQ desktop application.

This controller prepares investigation history data
for presentation in the GUI.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService


class HistoryController:
    """
    Controller responsible for retrieving investigation history.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
    ) -> None:
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

        return self._investigation_service.find_recent(limit)