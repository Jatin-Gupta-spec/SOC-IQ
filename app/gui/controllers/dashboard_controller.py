"""
Dashboard controller for the SOC-IQ desktop application.

This controller prepares dashboard data for presentation.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService

from app.gui.components.timeline.timeline_widget import (
    TimelineEvent,
)


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

    def get_recent_investigations(
        self,
        limit: int = 10,
    ) -> list[Investigation]:
        """
        Return the most recent investigations.

        Parameters
        ----------
        limit
            Maximum number of investigations.

        Returns
        -------
        list[Investigation]
            Recent investigations ordered from
            newest to oldest.
        """

        return self._investigation_service.find_recent(
            limit=limit,
        )

    def get_dashboard_timeline(
        self,
        limit: int = 10,
    ) -> list[TimelineEvent]:
        """
        Return timeline events representing the
        most recent investigations.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=limit,
            )
        )

        timeline: list[TimelineEvent] = []

        for investigation in investigations:

            timeline.append(
                TimelineEvent(
                    timestamp=investigation.analyzed_at.strftime(
                        "%H:%M",
                    ),
                    title=investigation.report_name,
                    description=(
                        f"Severity: {investigation.severity} | "
                        f"Risk Score: {investigation.risk_score}"
                    ),
                )
            )

        return timeline