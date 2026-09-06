"""
JSON exporter for SOC-IQ.

Exports an InvestigationReport
as a JSON report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.reporting.atomic_write import atomic_write
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

        MAX-21B-3 Part 2: written atomically via `atomic_write` --
        the complete JSON is written to a temporary file in the same
        directory and only then moved onto `output_path`, so a crash,
        disk-full condition, or interrupted write can never leave a
        truncated `output_path` or destroy a previously-valid export
        that was being overwritten (MAX-21A F3).
        """

        try:
            report_data = {
                "investigation_id": report.investigation_id,
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

            def _write(tmp_path: Path) -> None:
                with tmp_path.open(
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        report_data,
                        file,
                        indent=4,
                        ensure_ascii=False,
                    )
                    file.flush()
                    os.fsync(file.fileno())

            atomic_write(output_path, _write)

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export JSON report: {error}"
            ) from error