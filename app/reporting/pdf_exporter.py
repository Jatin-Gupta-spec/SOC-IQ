"""
PDF exporter for SOC-IQ.

Exports an InvestigationReport as a
professional PDF report.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
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

        # ==================================================
        # Header
        # ==================================================

        pdf.setFillColor(
            colors.HexColor("#2563EB")
        )

        pdf.rect(
            0,
            height - 70,
            width,
            70,
            fill=True,
            stroke=False,
        )

        pdf.setFillColor(
            colors.white
        )

        pdf.setFont(
            "Helvetica-Bold",
            24,
        )

        pdf.drawString(
            40,
            height - 42,
            "SOC-IQ Investigation Report",
        )

        pdf.setFont(
            "Helvetica",
            11,
        )

        pdf.drawString(
            42,
            height - 60,
            "Security Operations & Intelligence Platform",
        )

        pdf.setFillColor(
            colors.black
        )

        y = height - 95

        # ==================================================
        # Report Information
        # ==================================================

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

        # ==========================================
        # Executive Summary
        # ==========================================

        y -= 45

        pdf.setFont(
            "Helvetica-Bold",
            18,
        )

        pdf.drawString(
            50,
            y,
            "Executive Summary",
        )

        y -= 30

        pdf.setFont(
            "Helvetica",
            12,
        )

        pdf.drawString(
            60,
            y,
            f"Risk Score: {report.risk_score}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"Severity: {report.severity}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"Confidence: {report.confidence * 100:.0f}%",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"Status: {report.status}",
        )

        # ==========================================
        # Investigation Details
        # ==========================================

        y -= 45

        pdf.setFont(
            "Helvetica-Bold",
            18,
        )

        pdf.drawString(
            50,
            y,
            "Investigation Details",
        )

        y -= 30

        pdf.setFont(
            "Helvetica",
            12,
        )

        pdf.drawString(
            60,
            y,
            f"Report Name: {report.report_name}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"Analysis Time: {report.analyzed_at}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"IOC Score: {report.ioc_score}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"Threat Intelligence Score: {report.threat_intel_score}",
        )

        y -= 20

        pdf.drawString(
            60,
            y,
            f"CVE Score: {report.cve_score}",
        )

        pdf.save()

        return output_path