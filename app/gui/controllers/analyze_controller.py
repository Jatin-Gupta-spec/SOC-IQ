"""
Analyze controller for the SOC-IQ desktop application.

This controller acts as the bridge between the GUI
and the SOC-IQ analysis engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.analyzer import analyze_report


class AnalyzeController:
    """
    Controller responsible for launching report analysis.
    """

    def analyze(
        self,
        report_path: str,
    ) -> dict[str, Any]:
        """
        Analyze the selected report.

        Args:
            report_path:
                Path to the report selected by the user.

        Returns:
            Complete analysis results.
        """

        return analyze_report(
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

        return Path(report_path).is_file()