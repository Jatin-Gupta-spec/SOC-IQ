"""
JSON exporter for SOC-IQ.

Exports an InvestigationReport
as a JSON report.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.reporting.models import InvestigationReport


class JSONReportExporter:
    """
    Exports InvestigationReport objects
    as JSON files.
    """

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report
        to a JSON file.
        """

        try:
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            report_data = {
                "report_name": report.report_name,
                "analyzed_at": str(report.analyzed_at),
                "status": report.status,
                "risk_score": report.risk_score,
                "severity": report.severity,
                "confidence": report.confidence,
                "ioc_score": report.ioc_score,
                "threat_intel_score": report.threat_intel_score,
                "cve_score": report.cve_score,
                "iocs": report.iocs,
                "threat_intelligence": report.threat_intelligence,
            }

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    report_data,
                    file,
                    indent=4,
                    ensure_ascii=False,
                )

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export JSON report: {error}"
            ) from error