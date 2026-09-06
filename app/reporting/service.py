"""
Reporting service for SOC-IQ.

Coordinates creation of investigation reports
and delegates export operations to exporters.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.database.models import Investigation
from app.reporting.builder import ReportBuilder
from app.reporting.export_manager import ExportManager
from app.reporting.models import InvestigationReport


class ReportingService:
    """
    Service responsible for exporting
    investigation reports.
    """

    def build_default_filename(
        self,
        extension: str = "html",
    ) -> str:
        """
        Build the default filename for
        exported investigation reports.
        """

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S",
        )

        return (
            f"SOC-IQ_Investigation_"
            f"{timestamp}.{extension}"
        )

    def _build_report(
        self,
        investigation: Investigation,
    ) -> InvestigationReport:
        """
        Build an InvestigationReport
        from an Investigation.

        Delegates to `ReportBuilder` so there is a single place
        that maps `Investigation` -> `InvestigationReport` fields,
        rather than duplicating that mapping here.
        """

        return ReportBuilder.build(investigation)

    def export_html(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as an HTML report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_html(
            report,
            output_path,
        )

    def export_json(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as a JSON report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_json(
            report,
            output_path,
        )

    def export_markdown(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as a Markdown report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_markdown(
            report,
            output_path,
        )

    def export_pdf(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as a PDF report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_pdf(
            report,
            output_path,
        )