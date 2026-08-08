"""
Analyze controller for the SOC-IQ desktop application.

This controller acts as the bridge between the GUI
and the application service layer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from app.gui.services.analysis_service import (
    AnalysisService,
)

logger = logging.getLogger(__name__)


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
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze the selected report.

        Parameters
        ----------
        report_path
            Path to the selected report.

        Returns
        -------
        dict
            Analysis result returned by the
            backend analysis service.

        Raises
        ------
        FileNotFoundError
            If ``report_path`` is empty, or does not point to an
            existing file. Previously this method trusted the
            caller to have already called ``validate_report``
            first; if it was ever invoked directly (e.g. from the
            worker, or a future caller) with a bad path, the
            underlying service would be asked to analyze a
            nonexistent/invalid file. Validating here means an
            invalid report can never reach the analysis service and
            come back looking like a legitimate result.
        """

        if not self.validate_report(report_path):
            logger.warning(
                "Rejected analysis request for invalid report "
                "path: %r",
                report_path,
            )
            raise FileNotFoundError(
                f"Report path is missing or invalid: {report_path!r}"
            )

        return self._analysis_service.analyze(
            Path(report_path),
            progress_callback=progress_callback,
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