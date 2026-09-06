from __future__ import annotations

from app.database.service import InvestigationService
from app.services.dashboard_aggregation import compute_ioc_distribution


class DashboardIOCDistributionService:
    """
    Builds IOC distribution statistics for the dashboard.
    """

    def __init__(
        self,
        investigation_service: InvestigationService,
    ) -> None:
        self._investigation_service = (
            investigation_service
        )

    def get_distribution(
        self,
    ) -> dict[str, int]:
        """
        Return IOC counts grouped by type.

        Delegates to `app.services.dashboard_aggregation
        .compute_ioc_distribution` (Phase 4H Part 1) -- same
        calculation as before, extracted so the new
        `get_dashboard_summary` application command can reuse it
        without a second, independently-maintained copy of this loop.
        Return shape/value is unchanged.
        """

        investigations = (
            self._investigation_service.list_all()
        )

        return compute_ioc_distribution(investigations)