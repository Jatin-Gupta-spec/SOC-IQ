"""
Export manager for SOC-IQ.

Coordinates exporting investigation
reports to different formats.
"""

from __future__ import annotations

from pathlib import Path

from app.reporting.html_exporter import HTMLReportExporter
from app.reporting.json_exporter import JSONReportExporter
from app.reporting.markdown_exporter import MarkdownReportExporter
from app.reporting.pdf_exporter import PDFReportExporter
from app.reporting.models import InvestigationReport

class ExportManager:
    """
    Coordinates exporting investigation
    reports to different formats.
    """

    @staticmethod
    def export_html(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export a report as HTML.
        """

        return HTMLReportExporter.export(
            report,
            output_path,
        )

    @staticmethod
    def export_json(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export a report as JSON.
        """

        return JSONReportExporter.export(
            report,
            output_path,
        )

    @staticmethod
    def export_markdown(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export a report as Markdown.
        """

        return MarkdownReportExporter.export(
            report,
            output_path,
        )

    @staticmethod
    def export_pdf(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export a report as PDF.
        """

        return PDFReportExporter.export(
            report,
            output_path,
        )