"""
Dashboard controller for the SOC-IQ desktop application.

This controller prepares executive overview data for presentation.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService
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

    def get_summary(self) -> dict[str, str]:
        """
        Return dashboard summary information.
        """

        investigations = self._investigation_service.list_all()

        report_count = len(investigations)

        total_iocs = sum(
            sum(len(values) for values in investigation.iocs.values())
            for investigation in investigations
        )

        high_risk = sum(
            1
            for investigation in investigations
            if (investigation.severity or "").upper() in {"HIGH", "CRITICAL"}
        )

        return {
            "reports": str(report_count),
            "iocs": str(total_iocs),
            "high_risk": str(high_risk),
            "database": "Connected",
        }

    def get_threat_status(self) -> tuple[str, BadgeType]:
        """
        Evaluate overall system threat level based on active investigations.
        """
        investigations = self._investigation_service.list_all()

        if not investigations:
            return ("NORMAL", BadgeType.SUCCESS)

        critical_count = sum(
            1
            for inv in investigations
            if (inv.severity or "").upper() == "CRITICAL"
        )

        high_count = sum(
            1
            for inv in investigations
            if (inv.severity or "").upper() == "HIGH"
        )

        if critical_count > 0:
            return ("CRITICAL ALERT", BadgeType.CRITICAL)
        elif high_count > 0:
            return ("ELEVATED", BadgeType.WARNING)
        else:
            return ("NORMAL", BadgeType.SUCCESS)

    def get_latest_investigation(self) -> Investigation | None:
        """
        Return the most recently analyzed investigation.
        """

        investigations = self._investigation_service.find_recent(limit=1)

        if not investigations:
            return None

        return investigations[0]

    def get_recent_investigations(self, limit: int = 5) -> list[Investigation]:
        """
        Return the most recent investigations.
        """

        return self._investigation_service.find_recent(limit=limit)

    def get_dashboard_timeline(self, limit: int = 6) -> list[TimelineEvent]:
        """
        Return timeline events representing the most recent investigations.
        """

        investigations = self._investigation_service.find_recent(limit=limit)

        timeline: list[TimelineEvent] = []

        for investigation in investigations:
            timeline.append(
                TimelineEvent(
                    timestamp=investigation.analyzed_at.strftime("%H:%M"),
                    title=investigation.report_name,
                    description=f"Risk Score: {investigation.risk_score}",
                    severity=investigation.severity,
                    source="Investigation Engine",
                    icon="🛡",
                )
            )

        return timeline

    def get_system_status(self) -> dict[str, str]:
        """
        Return current system health information.
        """

        latest = self.get_latest_investigation()

        if latest is None:
            last_analysis = "Never"
        else:
            last_analysis = latest.analyzed_at.strftime("%d %b %Y %H:%M")

        return {
            "database": "Connected",
            "repository": "Operational",
            "analysis_engine": "Ready",
            "virustotal": "API Key Missing",
            "last_analysis": last_analysis,
        }