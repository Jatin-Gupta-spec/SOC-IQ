"""
SOC-IQ
Dashboard Statistics Service

Calculates dashboard metrics from stored investigations.
"""

from __future__ import annotations

from app.database.service import InvestigationService
from app.services.dashboard_aggregation import compute_dashboard_metrics


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

        Delegates the actual counting to `app.services
        .dashboard_aggregation.compute_dashboard_metrics` (Phase 4H
        Part 1) -- same calculation as before, extracted so the new
        `get_dashboard_summary` application command can reuse it
        (as real `int`s) without a second, independently-maintained
        copy. This method's own return shape/values are unchanged:
        still `dict[str, str]`, still including the static
        `"database": "Connected"` field the GUI already relies on.
        """

        investigations = (
            self._investigation_service.list_all()
        )

        metrics = compute_dashboard_metrics(investigations)

        return {
            "reports": str(metrics["report_count"]),
            "iocs": str(metrics["total_iocs"]),
            "high_risk": str(metrics["high_risk"]),
            "database": "Connected",
        }