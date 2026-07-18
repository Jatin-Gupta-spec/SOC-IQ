"""
Investigation workspace page for the SOC-IQ desktop application.

This page provides the primary analyst workspace used to
review completed investigations.
"""

from __future__ import annotations

from app.database.models import Investigation
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.events.application_state import (
    ApplicationState,
)
from app.gui.widgets.badge import Badge
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.key_value_row import KeyValueRow
from app.gui.widgets.page_container import PageContainer


class InvestigationWorkspacePage(QWidget):
    """
    Main analyst investigation workspace.
    """

    def __init__(self) -> None:
        super().__init__()

        self._container = PageContainer(
            title="Investigation Workspace",
            description=(
                "Review investigation details, extracted IOCs, "
                "threat intelligence, and risk assessment."
            ),
        )

        self._report_name_row = KeyValueRow(
            "Report Name",
            "Waiting...",
        )

        self._status_row = KeyValueRow(
            "Status",
            "Waiting...",
        )

        self._risk_score_row = KeyValueRow(
            "Risk Score",
            "0",
        )

        self._severity_badge = Badge(
            "Waiting...",
        )

        self._ioc_summary_label = QLabel(
            "Waiting for investigation..."
        )

        self._threat_summary_label = QLabel(
            "Waiting for investigation..."
        )

        self._risk_summary_label = QLabel(
            "Waiting for investigation..."
        )

        self._build_ui()

        self.refresh()

    def _build_ui(self) -> None:
        """
        Build the workspace layout.
        """

        layout = self._container.content_layout()

        # --------------------------------------------------
        # Investigation Summary
        # --------------------------------------------------

        summary = DetailSection(
            "Investigation Summary",
            "General information about the investigation.",
        )

        summary.add_widget(
            self._report_name_row
        )

        summary.add_widget(
            self._status_row
        )

        severity_row = KeyValueRow(
            "Severity",
            "",
        )

        severity_row.layout().addWidget(
            self._severity_badge
        )

        summary.add_widget(
            severity_row
        )

        summary.add_widget(
            self._risk_score_row
        )

        layout.addWidget(summary)

        # --------------------------------------------------
        # IOC Summary
        # --------------------------------------------------

        ioc_section = DetailSection(
            "IOC Summary",
            "Extracted indicators of compromise.",
        )

        ioc_section.add_widget(
            self._ioc_summary_label
        )

        layout.addWidget(ioc_section)

        # --------------------------------------------------
        # Threat Intelligence
        # --------------------------------------------------

        threat_section = DetailSection(
            "Threat Intelligence",
            "VirusTotal enrichment results.",
        )

        threat_section.add_widget(
            self._threat_summary_label
        )

        layout.addWidget(threat_section)

        # --------------------------------------------------
        # Risk Assessment
        # --------------------------------------------------

        risk_section = DetailSection(
            "Risk Assessment",
            "Overall investigation risk.",
        )

        risk_section.add_widget(
            self._risk_summary_label
        )

        layout.addWidget(risk_section)

        layout.addStretch()

        root_layout = QVBoxLayout()

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.addWidget(
            self._container
        )

        self.setLayout(
            root_layout
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display an investigation in the workspace.
        """

        self._report_name_row.set_value(
            investigation.report_name,
        )

        self._status_row.set_value(
            investigation.status,
        )

        self._severity_badge.set_text(
            investigation.severity,
        )

        self._risk_score_row.set_value(
            str(
                investigation.risk_score,
            )
        )

        total_iocs = sum(
            len(values)
            for values in investigation.iocs.values()
        )

        self._ioc_summary_label.setText(
            f"{total_iocs} indicator(s) extracted."
        )

        hashes = investigation.threat_intelligence.get(
            "hashes",
            [],
        )

        self._threat_summary_label.setText(
            f"{len(hashes)} threat intelligence result(s)."
        )

        self._risk_summary_label.setText(
            (
                f"Overall Severity: "
                f"{investigation.severity}"
            )
        )

    def refresh(self) -> None:
        """
        Refresh the workspace using the shared
        application state.
        """

        investigation = (
            ApplicationState.current_investigation
        )

        if investigation is None:
            return

        self.load_investigation(
            investigation,
        )