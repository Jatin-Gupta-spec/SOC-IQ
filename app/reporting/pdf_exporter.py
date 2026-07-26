"""
PDF exporter for SOC-IQ.

Exports an InvestigationReport as a
professional PDF report.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

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
        """

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pdf = canvas.Canvas(
            str(output_path),
        )

        width, height = (
            8.5 * inch,
            11 * inch,
        )

        pdf.setTitle(
            report.report_name,
        )

        y = height - 60

        pdf.setFont(
            "Helvetica-Bold",
            22,
        )

        pdf.drawString(
            50,
            y,
            "SOC-IQ Investigation Report",
        )

        y -= 40

        pdf.setFont(
            "Helvetica",
            12,
        )

        pdf.drawString(
            50,
            y,
            f"Report: {report.report_name}",
        )

        y -= 20

        pdf.drawString(
            50,
            y,
            f"Generated: {report.analyzed_at}",
        )

        y -= 20

        pdf.drawString(
            50,
            y,
            "Version: 1.0.0",
        )

        pdf.save()

        return output_path