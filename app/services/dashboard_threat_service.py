"""
SOC-IQ
Dashboard Threat Service

Calculates the overall dashboard threat level
from stored investigations.
"""

from __future__ import annotations

from app.database.service import InvestigationService
from app.gui.components.feedback.status_badge import BadgeType


class DashboardThreatService:
    """
    Provides dashboard threat level information.
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

    def get_threat_status(
        self,
    ) -> tuple[str, BadgeType]:
        """
        Return the overall dashboard threat level.
        """

        investigations = (
            self._investigation_service.list_all()
        )

        if not investigations:
            return (
                "NORMAL",
                BadgeType.SUCCESS,
            )

        critical_count = sum(
            1
            for investigation in investigations
            if (
                investigation.severity or ""
            ).upper() == "CRITICAL"
        )

        high_count = sum(
            1
            for investigation in investigations
            if (
                investigation.severity or ""
            ).upper() == "HIGH"
        )

        if critical_count > 0:
            return (
                "CRITICAL ALERT",
                BadgeType.CRITICAL,
            )

        if high_count > 0:
            return (
                "ELEVATED",
                BadgeType.WARNING,
            )

        return (
            "NORMAL",
            BadgeType.SUCCESS,
        )