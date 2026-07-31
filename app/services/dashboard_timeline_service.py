"""
SOC-IQ
Dashboard Timeline Service

Provides timeline events for the dashboard.
"""

from __future__ import annotations

from app.database.service import InvestigationService
from app.gui.components.timeline.timeline_widget import TimelineEvent


class DashboardTimelineService:
    """
    Creates dashboard timeline events from investigations.
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

    def get_timeline(
        self,
        limit: int = 6,
    ) -> list[TimelineEvent]:
        """
        Return recent investigation timeline events.
        """

        investigations = (
            self._investigation_service.find_recent(
                limit=limit
            )
        )

        timeline: list[TimelineEvent] = []

        for investigation in investigations:

            severity = (
                investigation.severity or "INFO"
            ).upper()

            icon = self._icon_for_severity(
                severity
            )

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
                    severity=severity,
                    source="Investigation Engine",
                    icon=icon,
                )
            )

        return timeline

    def _icon_for_severity(
        self,
        severity: str,
    ) -> str:
        """
        Return an icon for a severity level.
        """

        icons = {
            "CRITICAL": "🚨",
            "HIGH": "🛡",
            "MEDIUM": "⚠",
            "LOW": "ℹ",
            "INFO": "📄",
        }

        return icons.get(
            severity.upper(),
            "📄",
        )