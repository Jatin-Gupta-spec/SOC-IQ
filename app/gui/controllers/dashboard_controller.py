"""
Dashboard controller for the SOC-IQ desktop application.

This controller prepares executive overview data for presentation.
"""

from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


class DashboardController:
    """
    Controller responsible for preparing dashboard information.

    Every accessor below logs and re-raises on failure rather than
    swallowing the exception. A backend/service failure must never
    be indistinguishable from a legitimate empty result (no
    investigations yet, no threats detected, etc.) — callers are
    expected to catch and present failures explicitly instead of
    silently rendering "0" / "[]" / "healthy" for a broken backend.
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

        Raises
        ------
        Exception
            Propagated (after logging) if the statistics service
            fails. Callers must not treat this the same as a
            legitimate empty summary.
        """

        try:
            return self._statistics.get_summary()
        except Exception:
            logger.exception("Failed to load dashboard summary")
            raise

    def get_threat_status(
        self,
    ) -> tuple[str, BadgeType]:
        """
        Return current dashboard threat level.

        Raises
        ------
        Exception
            Propagated (after logging) if the threat service fails.
            A failed lookup must never be reported to the user as
            "UNKNOWN"/default — that reads as a legitimate status
            rather than a broken data source.
        """

        try:
            return self._threat_service.get_threat_status()
        except Exception:
            logger.exception("Failed to load threat status")
            raise

    def get_latest_investigation(
        self,
    ) -> Investigation | None:
        """
        Return latest investigation, or ``None`` if there genuinely
        are none yet.

        Raises
        ------
        Exception
            Propagated (after logging) if the lookup fails. Only a
            real "no investigations" result from the service should
            surface as ``None``.
        """

        try:
            return (
                self._investigation_service_dashboard.get_latest()
            )
        except Exception:
            logger.exception("Failed to load latest investigation")
            raise

    def get_recent_investigations(
        self,
        limit: int = 5,
    ) -> list[Investigation]:
        """
        Return recent investigations.

        Raises
        ------
        Exception
            Propagated (after logging) if retrieval fails. A failure
            must not be reported as an empty list, since that is
            indistinguishable from "no recent investigations".
        """

        try:
            return (
                self._investigation_service_dashboard.get_recent(
                    limit
                )
            )
        except Exception:
            logger.exception("Failed to load recent investigations")
            raise

    def get_dashboard_timeline(
        self,
        limit: int = 6,
    ) -> list[TimelineEvent]:
        """
        Return dashboard timeline events.

        Raises
        ------
        Exception
            Propagated (after logging) if the timeline service fails.
        """

        try:
            return self._timeline_service.get_timeline(
                limit
            )
        except Exception:
            logger.exception("Failed to load dashboard timeline")
            raise

    def get_ioc_distribution(
        self,
    ) -> dict[str, int]:
        """
        Return IOC distribution statistics.

        Raises
        ------
        Exception
            Propagated (after logging) if the distribution service
            fails.
        """

        try:
            return self._ioc_distribution.get_distribution()
        except Exception:
            logger.exception("Failed to load IOC distribution")
            raise

    def get_system_status(
        self,
    ) -> dict[str, str]:
        """
        Return current application component status.

        Raises
        ------
        Exception
            Propagated (after logging) if the health check itself
            fails to run. This is distinct from the health check
            running successfully and reporting a component as
            unhealthy — that legitimate result is returned as-is.
        """

        try:
            return self._system_health.get_status()
        except Exception:
            logger.exception("Failed to load system status")
            raise

    def get_threat_feed(
        self,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Return dashboard threat feed.

        Raises
        ------
        Exception
            Propagated (after logging) if the feed service fails. A
            failure must not be reported as an empty feed.
        """

        try:
            return self._threat_feed_service.get_feed(
                limit
            )
        except Exception:
            logger.exception("Failed to load threat feed")
            raise