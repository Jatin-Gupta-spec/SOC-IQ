"""
Markdown exporter for SOC-IQ.

Exports an InvestigationReport
as a Markdown report.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.reporting.atomic_write import atomic_write
from app.reporting.models import InvestigationReport

class MarkdownReportExporter:
    """
    Exports InvestigationReport objects
    as Markdown files.
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
        Export an investigation report
        to a Markdown file.

        MAX-21B-3 Part 2: written atomically via `atomic_write` (see
        `json_exporter.py` for the rationale) -- closes MAX-21A F3
        for the Markdown format.
        """

        try:
            investigation_id = (
                report.investigation_id
                if report.investigation_id is not None
                else "N/A"
            )

            markdown = f"""# SOC-IQ Investigation Report

            ## Report Information

            - **Investigation ID:** {investigation_id}
            - **Report Name:** {report.report_name}
            - **Analyzed At:** {report.analyzed_at}
            - **Status:** {report.status}
            - **Risk Score:** {report.risk_score}
            - **Severity:** {report.severity}
            - **Confidence:** {report.confidence:.2f}

            ## Scores

            - IOC Score: {report.ioc_score}
            - Threat Intelligence Score: {report.threat_intel_score}
            - CVE Score: {report.cve_score}

            ## IOC Summary
            """

            for ioc_type, values in report.iocs.items():
                markdown += f"\n### {ioc_type.replace('_', ' ').title()}\n\n"

                if values:
                    for value in values:
                        markdown += f"- {value}\n"
                else:
                    markdown += "- None\n"

            markdown += "\n## Threat Intelligence\n\n"

            ti_rows: list[str] = []

            for category, value_field, type_label in (
                MarkdownReportExporter._TI_CATEGORIES
            ):
                records = report.threat_intelligence.get(category, []) or []

                for item in records:
                    ti_rows.append(
                        f"| {item.get(value_field, '')} "
                        f"| {type_label} "
                        f"| {item.get('verdict', 'Unknown')} "
                        f"| {item.get('detection_ratio', 'N/A')} |\n"
                    )

            if ti_rows:
                markdown += "| Indicator | Type | Verdict | Detection Ratio |\n"
                markdown += "| --- | --- | --- | --- |\n"
                markdown += "".join(ti_rows)
            else:
                markdown += "No threat intelligence available.\n"

            def _write(tmp_path: Path) -> None:
                with tmp_path.open(
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(markdown)
                    file.flush()
                    os.fsync(file.fileno())

            atomic_write(output_path, _write)

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export Markdown report: {error}"
            ) from error
        