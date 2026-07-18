"""
GUI analysis service for the SOC-IQ desktop application.

This service coordinates the desktop GUI with the backend
analysis engine. It never performs analysis itself; instead,
it delegates to the backend and returns a fully populated
Investigation object ready for presentation.
"""

from __future__ import annotations

from pathlib import Path

from app.analyzer import analyze_report
from app.database.models import Investigation
from app.database.service import InvestigationService


class AnalysisService:
    """
    Service responsible for executing report analysis.

    The GUI interacts only with this service instead of
    calling the backend analysis engine directly.
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

    def analyze(
        self,
        report_path: Path,
    ) -> Investigation:
        """
        Analyze a malware report.

        Parameters
        ----------
        report_path
            Path to the report selected by the user.

        Returns
        -------
        Investigation
            Fully populated investigation loaded from
            the database after analysis completes.
        """

        analysis_result = analyze_report(
            report_path,
        )

        investigation_id = analysis_result[
            "investigation_id"
        ]

        investigation = (
            self._investigation_service.get_by_id(
                investigation_id,
            )
        )

        if investigation is None:
            raise RuntimeError(
                "Investigation could not be loaded "
                "after analysis."
            )

        return investigation