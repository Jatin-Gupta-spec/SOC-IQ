"""
Markdown exporter for SOC-IQ.

Exports an InvestigationReport
as a Markdown report.
"""

from __future__ import annotations

from pathlib import Path

from app.reporting.models import InvestigationReport

class MarkdownReportExporter:
    """
    Exports InvestigationReport objects
    as Markdown files.
    """

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report
        to a Markdown file.
        """

        try:
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            markdown = f"""# SOC-IQ Investigation Report

            ## Report Information

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

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                file.write(markdown)

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export Markdown report: {error}"
            ) from error
        