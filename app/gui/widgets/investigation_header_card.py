"""
Reusable investigation header card for SOC-IQ.

This widget displays the primary investigation
metadata shown at the top of the investigation
workspace.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.gui.widgets.badge import Badge
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.key_value_row import KeyValueRow


class InvestigationHeaderCard(DetailSection):
    """
    Displays investigation metadata.
    """

    def __init__(self) -> None:
        super().__init__(
            "Investigation Summary",
            (
                "General information about the "
                "current investigation."
            ),
        )

        self._investigation_id_row = KeyValueRow(
            "Investigation ID",
            "Waiting...",
        )

        self._report_name_row = KeyValueRow(
            "Report Name",
            "Waiting...",
        )

        self._analysis_time_row = KeyValueRow(
            "Analysis Time",
            "Waiting...",
        )

        self._status_row = KeyValueRow(
            "Status",
            "Waiting...",
        )

        self._ioc_count_row = KeyValueRow(
            "IOC Count",
            "0",
        )

        self._risk_score_row = KeyValueRow(
            "Risk Score",
            "0",
        )

        self._severity_badge = Badge(
            "Waiting...",
        )

        severity_row = KeyValueRow(
            "Severity",
        )

        severity_row.layout().addWidget(
            self._severity_badge,
        )

        self.add_widget(
            self._investigation_id_row,
        )

        self.add_widget(
            self._report_name_row,
        )

        self.add_widget(
            self._analysis_time_row,
        )

        self.add_widget(
            self._status_row,
        )

        self.add_widget(
            self._ioc_count_row,
        )

        self.add_widget(
            severity_row,
        )

        self.add_widget(
            self._risk_score_row,
        )

    def reset(self) -> None:
        """
        Reset displayed values.
        """

        self._investigation_id_row.set_value(
            "Waiting...",
        )

        self._report_name_row.set_value(
            "Waiting...",
        )

        self._analysis_time_row.set_value(
            "Waiting...",
        )

        self._status_row.set_value(
            "Waiting...",
        )

        self._ioc_count_row.set_value(
            "0",
        )

        self._severity_badge.set_text(
            "Waiting...",
        )

        self._risk_score_row.set_value(
            "0",
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display an investigation.
        """

        investigation_id = (
            str(investigation.investigation_id)
            if investigation.investigation_id is not None
            else "N/A"
        )

        self._investigation_id_row.set_value(
            investigation_id,
        )

        self._report_name_row.set_value(
            investigation.report_name,
        )

        self._analysis_time_row.set_value(
            investigation.analyzed_at.strftime(
                "%d %b %Y %H:%M",
            ),
        )

        self._status_row.set_value(
            investigation.status,
        )

        total_iocs = sum(
            len(values)
            for values in investigation.iocs.values()
        )

        self._ioc_count_row.set_value(
            str(total_iocs),
        )

        self._severity_badge.set_text(
            investigation.severity,
        )

        self._risk_score_row.set_value(
            str(
                investigation.risk_score,
            ),
        )