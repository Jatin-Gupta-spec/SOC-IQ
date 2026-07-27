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
from reportlab.platypus import Table, TableStyle

from app.reporting.models import InvestigationReport

PAGE_MARGIN = 40

HEADER_HEIGHT = 70

LINE_HEIGHT = 20

TABLE_ROW_HEIGHT = 22

PRIMARY_BLUE = colors.HexColor("#2563EB")

LIGHT_BLUE = colors.HexColor("#E0F2FE")

LIGHT_GREY = colors.HexColor("#F3F4F6")


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

        BOTTOM_MARGIN = 60

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

        pdf.setFillColor(
            colors.HexColor("#1E3A8A"),
        )

        pdf.drawString(
            50,
            y,
            "Executive Summary",
        )

        pdf.setStrokeColor(
            colors.HexColor("#2563EB"),
        )

        pdf.setLineWidth(
            1,
        )

        pdf.line(
            50,
            y - 5,
            width - 50,
            y - 5,
        )

        pdf.setFillColor(
            colors.black,
        )

        y -= 35

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

        pdf.setFillColor(
            colors.HexColor("#1E3A8A"),
        )

        pdf.drawString(
            50,
            y,
            "Investigation Details",
        )

        pdf.setStrokeColor(
            colors.HexColor("#2563EB"),
        )

        pdf.setLineWidth(
            1,
        )

        pdf.line(
            50,
            y - 5,
            width - 50,
            y - 5,
        )

        pdf.setFillColor(
            colors.black,
        )

        y -= 35

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

        # ==========================================
        # IOC Summary
        # ==========================================

        y -= 45

        pdf.setFont(
            "Helvetica-Bold",
            18,
        )

        pdf.setFillColor(
            colors.HexColor("#1E3A8A"),
        )

        pdf.drawString(
            50,
            y,
            "IOC Summary",
        )

        pdf.setStrokeColor(
            colors.HexColor("#2563EB"),
        )

        pdf.setLineWidth(
            1,
        )

        pdf.line(
            50,
            y - 5,
            width - 50,
            y - 5,
        )

        pdf.setFillColor(
            colors.black,
        )

        y -= 35

        table_data = [
            [
                "IOC Type",
                "Count",
            ]
        ]

        for ioc_type, values in report.iocs.items():

            table_data.append(
                [
                    ioc_type.replace(
                        "_",
                        " ",
                    ).title(),
                    str(len(values)),
                ]
            )

        table = Table(
            table_data,
            colWidths=[
                300,
                100,
            ],
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#2563EB"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.grey,
                    ),
                    (
                        "BACKGROUND",
                        (0, 1),
                        (-1, -1),
                        colors.whitesmoke,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, 0),
                        8,
                    ),
                    (
                        "TOPPADDING",
                        (0, 1),
                        (-1, -1),
                        6,
                    ),
                ]
            )
        )

        table.wrapOn(
            pdf,
            width,
            height,
        )

        table_height = 20 * len(table_data)

        table.drawOn(
            pdf,
            50,
            y - table_height,
        )

        y -= table_height

        if y < BOTTOM_MARGIN + 150:

            pdf.showPage()

            y = height - 70

        # ==========================================
        # Threat Intelligence Summary
        # ==========================================

        y = y - (20 * len(table_data)) - 50

        pdf.setFont(
            "Helvetica-Bold",
            18,
        )

        pdf.drawString(
            50,
            y,
            "Threat Intelligence Summary",
        )

        y -= 30

        threat_table = [
            [
                "SHA256",
                "Verdict",
                "Detection",
            ]
        ]

        hashes = report.threat_intelligence.get(
            "hashes",
            [],
        )

        for item in hashes:

            threat_table.append(
                [
                    item.get(
                        "sha256",
                        "",
                    )[:24] + "...",
                    item.get(
                        "verdict",
                        "Unknown",
                    ),
                    str(
                        item.get(
                            "detection_ratio",
                            "N/A",
                        )
                    ),
                ]
            )

        if len(threat_table) == 1:

            threat_table.append(
                [
                    "-",
                    "No Threat Intelligence",
                    "-",
                ]
            )

        table = Table(
            threat_table,
            colWidths=[
                250,
                120,
                100,
            ],
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#2563EB"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.grey,
                    ),
                    (
                        "BACKGROUND",
                        (0, 1),
                        (-1, -1),
                        colors.whitesmoke,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, 0),
                        8,
                    ),
                ]
            )
        )

        table.wrapOn(
            pdf,
            width,
            height,
        )

        table_height = 20 * len(threat_table)

        table.drawOn(
            pdf,
            50,
            y - table_height,
        )

        y -= table_height

        if y < BOTTOM_MARGIN:

            pdf.showPage()

            y = height - 70

        # ==========================================
        # Footer
        # ==========================================

        pdf.setStrokeColor(
            colors.grey,
        )

        pdf.line(
            40,
            40,
            width - 40,
            40,
        )

        pdf.setFont(
            "Helvetica",
            9,
        )

        pdf.setFillColor(
            colors.grey,
        )

        pdf.drawString(
            45,
            25,
            "SOC-IQ | Security Operations & Intelligence Platform",
        )

        pdf.drawRightString(
            width - 45,
            25,
            "Page 1",
        )

        pdf.save()

        return output_path