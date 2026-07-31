"""
Dashboard Threat Feed Service

Provides recent threat intelligence entries
for the SOC-IQ dashboard.
"""

from __future__ import annotations

from app.database.service import InvestigationService


class DashboardThreatFeedService:
    """
    Builds dashboard threat feed data.
    """

    def __init__(
        self,
        investigation_service: InvestigationService,
    ) -> None:
        self._investigation_service = (
            investigation_service
        )

    def get_feed(
        self,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """
        Return recent threat intelligence feed.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=limit,
            )
        )

        feed: list[dict[str, str]] = []

        for investigation in investigations:

            feed.append(
                {
                    "title": investigation.report_name,
                    "severity": investigation.severity,
                    "risk_score": str(
                        investigation.risk_score
                    ),
                    "time": investigation.analyzed_at.strftime(
                        "%d %b %H:%M"
                    ),
                }
            )

        return feed