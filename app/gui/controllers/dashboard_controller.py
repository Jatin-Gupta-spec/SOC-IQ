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
from app.services.dashboard_timeline_service import (
    DashboardTimelineService,
)
from app.services.dashboard_investigation_service import (
    DashboardInvestigationService,
)
from app.services.dashboard_threat_feed_service import (
    DashboardThreatFeedService,
)
from app.services.dashboard_ioc_distribution_service import (
    DashboardIOCDistributionService,
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

        self._timeline_service = DashboardTimelineService(
            self._investigation_service
        )

        self._ioc_distribution = (
            DashboardIOCDistributionService(
                self._investigation_service
            )
        )

        self._threat_feed_service = (
            DashboardThreatFeedService(
                self._investigation_service
            )
        )

        self._investigation_service_dashboard = (
            DashboardInvestigationService(
                self._investigation_service
            )
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
        Return latest investigation.
        """

        return (
            self._investigation_service_dashboard.get_latest()
        )

    def get_recent_investigations(
        self,
        limit: int = 5,
    ) -> list[Investigation]:
        """
        Return recent investigations.
        """

        return (
            self._investigation_service_dashboard.get_recent(
                limit
            )
        )

    def get_dashboard_timeline(
        self,
        limit: int = 6,
    ) -> list[TimelineEvent]:
        """
        Return dashboard timeline events.
        """

        return self._timeline_service.get_timeline(
            limit
        )

    def get_ioc_distribution(
        self,
    ) -> dict[str, int]:
        """
        Return IOC distribution statistics.
        """

        return self._ioc_distribution.get_distribution()

    def get_system_status(
        self,
    ) -> dict[str, str]:
        """
        Return current application component status.
        """

        return self._system_health.get_status()

    def get_threat_feed(
        self,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Return dashboard threat feed.
        """

        return self._threat_feed_service.get_feed(
            limit
        )