"""
Reporting service for SOC-IQ.

Coordinates creation of investigation reports
and delegates export operations to exporters.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.database.models import Investigation
from app.reporting.export_manager import ExportManager
from app.reporting.models import InvestigationReport


class ReportingService:
    """
    Service responsible for exporting
    investigation reports.
    """

    def build_default_filename(
        self,
        extension: str = "html",
    ) -> str:
        """
        Build the default filename for
        exported investigation reports.
        """

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S",
        )

        return (
            f"SOC-IQ_Investigation_"
            f"{timestamp}.{extension}"
        )

    def _build_report(
        self,
        investigation: Investigation,
    ) -> InvestigationReport:
        """
        Build an InvestigationReport
        from an Investigation.
        """

        return InvestigationReport(
            report_name=investigation.report_name,
            analyzed_at=investigation.analyzed_at,
            status=investigation.status,
            severity=investigation.severity,
            risk_score=investigation.risk_score,
            confidence=investigation.confidence,
            ioc_score=investigation.ioc_score,
            threat_intel_score=investigation.threat_intel_score,
            cve_score=investigation.cve_score,
            iocs=investigation.iocs,
            threat_intelligence=investigation.threat_intelligence,
        )

    def export_html(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as an HTML report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_html(
            report,
            output_path,
        )

    def export_json(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as a JSON report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_json(
            report,
            output_path,
        )

    def export_markdown(
        self,
        investigation: Investigation,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation as a Markdown report.
        """

        report = self._build_report(
            investigation,
        )

        return ExportManager.export_markdown(
            report,
            output_path,
        )