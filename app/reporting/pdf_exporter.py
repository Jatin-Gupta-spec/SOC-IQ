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

from app.reporting.atomic_write import atomic_write
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

    # Canonical mapping of each enrichable TI category (as stored on
    # `report.threat_intelligence`) to the record field holding the
    # indicator's value and a display label for the "Type" column.
    # Hashes stay first so existing hash-only reports render
    # identically to before Phase 3E.
    _TI_CATEGORIES: tuple[tuple[str, str, str], ...] = (
        ("hashes", "sha256", "SHA256"),
        ("ips", "ip", "IPv4"),
        ("domains", "domain", "Domain"),
        ("urls", "url", "URL"),
    )

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report to PDF.

        MAX-21B-3 Part 2: written atomically via `atomic_write` (see
        `json_exporter.py` for the rationale) -- closes MAX-21A F3
        for the PDF format. The actual reportlab rendering is
        unchanged and lives in `_render`; this method's only job is
        to point that rendering at a temporary file and only replace
        `output_path` once it has completed successfully.
        """

        try:
            def _write(tmp_path: Path) -> None:
                PDFReportExporter._render(report, tmp_path)

            atomic_write(output_path, _write)

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export PDF report: {error}"
            ) from error

    @staticmethod
    def _render(
        report: InvestigationReport,
        output_path: Path,
    ) -> None:
        """
        Render `report` as a PDF directly to `output_path`.

        This is the original (pre-MAX-21B-3) export body, unchanged
        except that it no longer returns a value -- `export` above is
        now the only public entry point and always writes to a
        temporary path via `atomic_write`, so `output_path` here is
        never the final user-facing destination.
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
            PRIMARY_BLUE,
        )

        pdf.rect(
            0,
            height - HEADER_HEIGHT,
            width,
            HEADER_HEIGHT,
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
            PAGE_MARGIN,
            height - 42,
            "SOC-IQ Investigation Report",
        )

        pdf.setFont(
            "Helvetica",
            11,
        )

        pdf.drawString(
            PAGE_MARGIN + 2,
            height - 60,
            "Security Operations & Intelligence Platform",
        )

        pdf.setFillColor(
            colors.black
        )

        y = height - HEADER_HEIGHT - 25

        # ==================================================
        # Report Information
        # ==================================================

        pdf.setFont(
            "Helvetica",
            12,
        )

        pdf.drawString(
            PAGE_MARGIN + 10,
            y,
            f"Report: {report.report_name}",
        )

        y -= LINE_HEIGHT

        pdf.drawString(
            PAGE_MARGIN + 10,
            y,
            f"Generated: {report.analyzed_at}",
        )

        y -= LINE_HEIGHT

        pdf.drawString(
            PAGE_MARGIN + 10,
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
            PRIMARY_BLUE,
        )

        pdf.drawString(
            PAGE_MARGIN,
            y,
            "Executive Summary",
        )

        pdf.setStrokeColor(
            PRIMARY_BLUE,
        )

        pdf.setLineWidth(
            1,
        )

        pdf.line(
            PAGE_MARGIN,
            y - 5,
            width - PAGE_MARGIN,
            y - 5,
        )

        pdf.setFillColor(
            LIGHT_BLUE,
        )

        pdf.roundRect(
            PAGE_MARGIN,
            y - 110,
            width - (PAGE_MARGIN * 2),
            100,
            8,
            fill=True,
            stroke=False,
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
            PAGE_MARGIN + 15,
            y,
            f"Risk Score: {report.risk_score}",
        )

        y -= 20

        pdf.drawString(
            PAGE_MARGIN + 15,
            y,
            f"Severity: {report.severity}",
        )

        y -= 20

        pdf.drawString(
            PAGE_MARGIN + 15,
            y,
            f"Confidence: {report.confidence * 100:.0f}%",
        )

        y -= 20

        pdf.drawString(
            PAGE_MARGIN + 15,
            y,
            f"Status: {report.status}",
        )

        y -= 50

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

        investigation_id = (
            report.investigation_id
            if report.investigation_id is not None
            else "N/A"
        )

        pdf.drawString(
            60,
            y,
            f"Investigation ID: {investigation_id}",
        )

        y -= 20

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
                "Indicator",
                "Type",
                "Verdict",
                "Detection",
            ]
        ]

        for category, value_field, type_label in (
            PDFReportExporter._TI_CATEGORIES
        ):

            records = (
                report.threat_intelligence.get(
                    category,
                    [],
                )
                or []
            )

            for item in records:

                value = str(
                    item.get(
                        value_field,
                        "",
                    )
                )

                if len(value) > 24:
                    value = value[:24] + "..."

                threat_table.append(
                    [
                        value,
                        type_label,
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
                    "-",
                    "No Threat Intelligence",
                    "-",
                ]
            )

        table = Table(
            threat_table,
            colWidths=[
                190,
                70,
                120,
                90,
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