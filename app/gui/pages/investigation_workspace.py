"""
Investigation workspace page for the SOC-IQ desktop application.

This page provides the primary analyst workspace used to
review completed investigations.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.events.application_state import (
    ApplicationState,
)
from app.gui.widgets.badge import Badge
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.key_value_row import KeyValueRow
from app.gui.widgets.page_container import PageContainer

from app.gui.widgets.ioc_summary_widget import (
    IOCSummaryWidget,
)

from app.gui.widgets.threat_intelligence_widget import (
    ThreatIntelligenceWidget,
)

from app.gui.widgets.risk_summary_widget import (
    RiskSummaryWidget,
)

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

        # ------------------------------------------
        # Investigation Summary
        # ------------------------------------------

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

        self._risk_score_row = KeyValueRow(
            "Risk Score",
            "0",
        )

        self._severity_badge = Badge(
            "Waiting...",
        )

        # ------------------------------------------
        # Section Labels
        # ------------------------------------------

        self._ioc_summary_widget = IOCSummaryWidget()

        self._threat_summary_widget = (
    ThreatIntelligenceWidget()
)

        self._risk_summary_widget = (
    RiskSummaryWidget()
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
            self._investigation_id_row
        )

        summary.add_widget(
            self._report_name_row
        )

        summary.add_widget(
            self._analysis_time_row
        )

        summary.add_widget(
            self._status_row
        )

        severity_row = KeyValueRow(
            "Severity",
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
            self._ioc_summary_widget
        )

        layout.addWidget(
            ioc_section
        )

        # --------------------------------------------------
        # Threat Intelligence
        # --------------------------------------------------

        threat_section = DetailSection(
            "Threat Intelligence",
            "VirusTotal enrichment results.",
        )

        threat_section.add_widget(
            self._threat_summary_widget
        )

        layout.addWidget(
            threat_section
        )

        # --------------------------------------------------
        # Risk Assessment
        # --------------------------------------------------

        risk_section = DetailSection(
            "Risk Assessment",
            "Overall investigation risk.",
        )

        risk_section.add_widget(
            self._risk_summary_widget
        )

        layout.addWidget(
            risk_section
        )

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

    def _reset_workspace(self) -> None:
        """
        Reset the workspace to its default state.
        """

        self._investigation_id_row.set_value(
            "Waiting..."
        )

        self._report_name_row.set_value(
            "Waiting..."
        )

        self._analysis_time_row.set_value(
            "Waiting..."
        )

        self._status_row.set_value(
            "Waiting..."
        )

        self._severity_badge.set_text(
            "Waiting..."
        )

        self._risk_score_row.set_value(
            "0"
        )

        self._ioc_summary_widget.reset()

        self._threat_summary_widget.reset()

        self._risk_summary_widget.reset()

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display an investigation in the workspace.
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
                "%Y-%m-%d %H:%M:%S UTC",
            )
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

        self._ioc_summary_widget.load_investigation(
    investigation,
)

        self._threat_summary_widget.load_investigation(
    investigation,
)

        self._risk_summary_widget.load_investigation(
    investigation,
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
            self._reset_workspace()
            return

        self.load_investigation(
            investigation,
        )