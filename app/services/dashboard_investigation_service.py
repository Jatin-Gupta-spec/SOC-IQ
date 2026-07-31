"""
SOC-IQ
Dashboard Investigation Service

Provides investigation data required by
the dashboard.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService


class DashboardInvestigationService:
    """
    Provides dashboard investigation data.
    """

    def __init__(
        self,
        investigation_service: InvestigationService,
    ) -> None:

        self._investigation_service = investigation_service

    def get_latest(
        self,
    ) -> Investigation | None:
        """
        Return latest investigation.
        """

        investigations = self._investigation_service.find_recent(
            limit=1
        )

        if not investigations:
            return None

        return investigations[0]

    def get_recent(
        self,
        limit: int = 5,
    ) -> list[Investigation]:
        """
        Return recent investigations.
        """

        return self._investigation_service.find_recent(
            limit=limit
        )