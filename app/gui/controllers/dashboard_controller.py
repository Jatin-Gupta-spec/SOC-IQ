"""
Dashboard controller for the SOC-IQ desktop application.

This controller prepares executive overview data for presentation.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService

from app.services.dashboard_statistics_service import (
    DashboardStatisticsService,
)
from app.services.dashboard_threat_service import (
    DashboardThreatService,
)
from app.services.system_health_service import (
    SystemHealthService,
)

from app.gui.components.feedback.status_badge import BadgeType
from app.gui.components.timeline.timeline_widget import TimelineEvent


class DashboardController:
    """
    Controller responsible for preparing dashboard information.
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

        self._statistics = DashboardStatisticsService(
            self._investigation_service
        )

        self._threat_service = DashboardThreatService(
            self._investigation_service
        )

        self._system_health = SystemHealthService()

    def get_summary(self) -> dict[str, str]:
        """
        Return dashboard summary information.
        """

        return self._statistics.get_summary()

    def get_threat_status(
        self,
    ) -> tuple[str, BadgeType]:
        """
        Return current dashboard threat level.
        """

        return self._threat_service.get_threat_status()

    def get_latest_investigation(
        self,
    ) -> Investigation | None:
        """
        Return the most recently analyzed investigation.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=1
            )
        )

        if not investigations:
            return None

        return investigations[0]

    def get_recent_investigations(
        self,
        limit: int = 5,
    ) -> list[Investigation]:
        """
        Return the most recent investigations.
        """

        return self._investigation_service.find_recent(
            limit=limit
        )

    def get_dashboard_timeline(
        self,
        limit: int = 6,
    ) -> list[TimelineEvent]:
        """
        Return timeline events representing
        the most recent investigations.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=limit
            )
        )

        timeline: list[TimelineEvent] = []

        for investigation in investigations:
            timeline.append(
                TimelineEvent(
                    timestamp=investigation.analyzed_at.strftime(
                        "%H:%M"
                    ),
                    title=investigation.report_name,
                    description=(
                        f"Risk Score: "
                        f"{investigation.risk_score}"
                    ),
                    severity=investigation.severity,
                    source="Investigation Engine",
                    icon="🛡",
                )
            )

        return timeline

    def get_system_status(
        self,
    ) -> dict[str, str]:
        """
        Return current application component status.
        """

        return self._system_health.get_status()