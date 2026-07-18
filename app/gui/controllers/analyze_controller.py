"""
Analyze controller for the SOC-IQ desktop application.

This controller acts as the bridge between the GUI
and the application service layer.
"""

from __future__ import annotations

from pathlib import Path

from app.database.models import Investigation
from app.gui.services.analysis_service import (
    AnalysisService,
)


class AnalyzeController:
    """
    Controller responsible for launching report analysis.
    """

    def __init__(
        self,
        analysis_service: AnalysisService | None = None,
    ) -> None:
        """
        Initialize the controller.
        """

        self._analysis_service = (
            analysis_service
            if analysis_service is not None
            else AnalysisService()
        )

    def analyze(
        self,
        report_path: str,
    ) -> Investigation:
        """
        Analyze the selected report.

        Parameters
        ----------
        report_path
            Path to the selected report.

        Returns
        -------
        Investigation
            Completed investigation loaded from
            the database.
        """

        return self._analysis_service.analyze(
            Path(report_path),
        )

    def validate_report(
        self,
        report_path: str,
    ) -> bool:
        """
        Validate the selected report path.
        """

        if not report_path:
            return False

        report = Path(report_path)

        return (
            report.exists()
            and report.is_file()
        )