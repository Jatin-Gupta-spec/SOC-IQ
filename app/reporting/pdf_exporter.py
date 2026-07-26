"""
PDF exporter for SOC-IQ.

Exports an InvestigationReport as a
professional PDF report.
"""

from __future__ import annotations

from pathlib import Path

from app.reporting.models import InvestigationReport


class PDFReportExporter:
    """
    Exports InvestigationReport objects
    as PDF files.
    """

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report to PDF.

        Returns:
            Path to the generated PDF.
        """

        raise NotImplementedError(
            "PDF exporter not implemented yet."
        )