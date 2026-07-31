"""
SOC-IQ
Dashboard Statistics Service

Calculates dashboard metrics from stored investigations.
"""

from __future__ import annotations

from app.database.service import InvestigationService


class DashboardStatisticsService:
    """
    Provides aggregated dashboard statistics.
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

    def get_summary(
        self,
    ) -> dict[str, str]:
        """
        Return dashboard KPI summary.
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
            if (
                investigation.severity or ""
            ).upper() in {
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