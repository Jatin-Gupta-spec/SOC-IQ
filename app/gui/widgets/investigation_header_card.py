"""
Reusable investigation header card for SOC-IQ.

This widget displays the primary investigation
metadata shown at the top of the investigation
workspace.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton

from app.database.models import Investigation
from app.gui.components.feedback.status_badge import StatusBadge
from app.gui.utils.badge_mapping import severity_to_badge_type
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.key_value_row import KeyValueRow


class InvestigationHeaderCard(DetailSection):
    """
    Displays investigation metadata.
    """

    export_requested = Signal()

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

        self._confidence_row = KeyValueRow(
            "Confidence",
            "0%",
        )

        self._threat_intel_row = KeyValueRow(
            "Threat Intelligence",
            "Waiting...",
        )

        self._severity_badge = StatusBadge(
            "WAITING...",
        )

        self._export_button = QPushButton(
            "Export Investigation Report",
        )

        self._export_button.clicked.connect(
            self.export_requested.emit,
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
            self._threat_intel_row,
        )

        self.add_widget(
            severity_row,
        )

        self.add_widget(
            self._risk_score_row,
        )

        self.add_widget(
            self._confidence_row,
        )

        self.add_widget(
            self._export_button,
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

        self._threat_intel_row.set_value(
            "Waiting...",
        )

        self._threat_intel_row.setToolTip("")

        self._severity_badge.set_text(
            "WAITING...",
        )

        self._severity_badge.set_badge_type(
            severity_to_badge_type("waiting..."),
        )

        self._risk_score_row.set_value(
            "0",
        )

        self._confidence_row.set_value(
            "0%",
        )

    def load_investigation(
        self,
        investigation: Investigation,
        threat_intel_overview: dict | None = None,
    ) -> None:
        """
        Display an investigation.

        Args:
            investigation:
                The investigation to display.
            threat_intel_overview:
                Optional result of
                `build_investigation_threat_intel_overview()`. When
                omitted, the Threat Intelligence row is left at its
                previous value -- callers that care about this row
                (currently `InvestigationWorkspacePage`) always pass
                it; it's optional here only so existing/other
                callers and tests that construct this widget for
                unrelated fields keep working unchanged.
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

        if threat_intel_overview is not None:

            self._threat_intel_row.set_value(
                threat_intel_overview["short_label"],
            )

            self._threat_intel_row.setToolTip(
                threat_intel_overview["message"],
            )

        self._severity_badge.set_text(
            investigation.severity,
        )

        self._risk_score_row.set_value(
            str(
                investigation.risk_score,
            ),
        )

        self._confidence_row.set_value(
            f"{investigation.confidence:.0%}",
        )