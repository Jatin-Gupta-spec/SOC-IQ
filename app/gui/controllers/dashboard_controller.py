"""
Dashboard controller for the SOC-IQ desktop application.

This controller prepares dashboard data for presentation.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService


class DashboardController:
    """
    Controller responsible for preparing
    dashboard information.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
    ) -> None:
        """
        Initialize the dashboard controller.
        """

        self._investigation_service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )

    def get_summary(self) -> dict[str, str]:
        """
        Return dashboard summary information.
        """

        investigations = (
            self._investigation_service.list_all()
        )

        report_count = len(
            investigations
        )

        total_iocs = sum(
            sum(
                len(values)
                for values in investigation.iocs.values()
            )
            for investigation in investigations
        )

        high_risk = sum(
            1
            for investigation in investigations
            if investigation.severity.upper()
            in {
                "HIGH",
                "CRITICAL",
            }
        )

        return {
            "reports": str(report_count),
            "iocs": str(total_iocs),
            "high_risk": str(high_risk),
            "database": "Connected",
        }

    def get_latest_investigation(
        self,
    ) -> Investigation | None:
        """
        Return the most recently analyzed investigation.

        Returns
        -------
        Investigation | None
            The latest investigation if one exists,
            otherwise None.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=1,
            )
        )

        if not investigations:
            return None

        return investigations[0]