"""
GUI analysis service for the SOC-IQ desktop application.

This service coordinates the desktop GUI with the backend
analysis engine. It never performs analysis itself; instead,
it delegates to the backend and returns the completed
investigation together with duplicate information.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.analyzer import analyze_report


class AnalysisService:
    """
    Service responsible for executing report analysis.

    The GUI interacts only with this service instead of
    calling the backend analysis engine directly.
    """

    def analyze(
        self,
        report_path: Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a malware report.

        Parameters
        ----------
        report_path
            Path to the report selected by the user.

        Returns
        -------
        dict
            Dictionary containing:

            investigation
                Completed Investigation object.

            existing
                True if an existing investigation
                was reused instead of creating a
                new one.
        """

        return analyze_report(
            report_path,
            progress_callback=progress_callback,
        )