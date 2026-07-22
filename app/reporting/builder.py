"""
Report builder for SOC-IQ.

Converts Investigation objects into reusable
InvestigationReport models.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.reporting.models import InvestigationReport


class ReportBuilder:
    """
    Builds InvestigationReport instances.
    """

    @staticmethod
    def build(
        investigation: Investigation,
    ) -> InvestigationReport:
        """
        Convert an Investigation into an
        InvestigationReport.
        """

        return InvestigationReport(
            report_name=investigation.report_name,
            analyzed_at=investigation.analyzed_at.isoformat(),
            status=investigation.status,
            severity=investigation.severity,
            risk_score=investigation.risk_score,
            confidence=investigation.confidence,
            ioc_score=investigation.ioc_score,
            threat_intel_score=(
                investigation.threat_intel_score
            ),
            cve_score=investigation.cve_score,
            iocs=investigation.iocs,
            threat_intelligence=(
                investigation.threat_intelligence
            ),
        )