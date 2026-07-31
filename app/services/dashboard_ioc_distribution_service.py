from __future__ import annotations

from collections import Counter

from app.database.service import InvestigationService


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
        """

        investigations = (
            self._investigation_service.list_all()
        )

        counter: Counter[str] = Counter()

        for investigation in investigations:
            for ioc_type, values in (
                investigation.iocs.items()
            ):
                counter[ioc_type] += len(values)

        return dict(counter)