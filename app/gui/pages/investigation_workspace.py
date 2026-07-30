"""
Investigation workspace page for the SOC-IQ desktop application.

Provides the primary analyst workbench organized into clean tabbed sections
(Overview & Metrics, IOC Analysis, Threat Intelligence) to eliminate excessive
scrolling while maintaining deep-dive forensic clarity.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.investigation_header_card import InvestigationHeaderCard
from app.gui.widgets.investigation_metrics_widget import InvestigationMetricsWidget
from app.gui.widgets.investigation_timeline_widget import InvestigationTimelineWidget
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget
from app.gui.widgets.ioc_summary_widget import IOCSummaryWidget
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.risk_summary_widget import RiskSummaryWidget
from app.gui.widgets.threat_intelligence_widget import ThreatIntelligenceWidget


class InvestigationWorkspacePage(QWidget):
    """
    Main analyst investigation workspace.
    """

    status_message = Signal(str)
    export_investigation_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._container = PageContainer(
            title="Analyst Investigation Workspace",
            description=(
                "Deep-dive forensic analysis, extracted indicators, threat "
                "intelligence, and risk breakdown."
            ),
        )

        self._header_card = InvestigationHeaderCard()

        # Workspace Tabbed Views
        self._tab_widget = QTabWidget()

        # Section Widgets
        self._ioc_summary_widget = IOCSummaryWidget()
        self._ioc_details_widget = IOCDetailsWidget()
        self._threat_summary_widget = ThreatIntelligenceWidget()
        self._risk_summary_widget = RiskSummaryWidget()
        self._metrics_widget = InvestigationMetricsWidget()
        self._timeline_widget = InvestigationTimelineWidget()

        self._build_ui()
        self._connect_signals()

        self.refresh()

    def _build_ui(self) -> None:
        """
        Build the tabbed workspace layout.
        """
        layout = self._container.content_layout()

        # 1. Top Persistent Header Card
        layout.addWidget(self._header_card)

        # 2. Build Tab Pages
        tab_overview = QWidget()
        overview_layout = QVBoxLayout(tab_overview)
        overview_layout.setContentsMargins(0, 16, 0, 0)
        overview_layout.setSpacing(16)

        risk_sec = DetailSection("Risk Assessment", "Overall investigation risk posture.")
        risk_sec.add_widget(self._risk_summary_widget)
        overview_layout.addWidget(risk_sec)

        metrics_sec = DetailSection("Scoring & Metrics", "Detailed threat calculation breakdown.")
        metrics_sec.add_widget(self._metrics_widget)
        overview_layout.addWidget(metrics_sec)

        timeline_sec = DetailSection("Investigation Timeline", "Chronological event logs.")
        timeline_sec.add_widget(self._timeline_widget)
        overview_layout.addWidget(timeline_sec)

        overview_layout.addStretch()

        # Tab 2: IOCs
        tab_iocs = QWidget()
        iocs_layout = QVBoxLayout(tab_iocs)
        iocs_layout.setContentsMargins(0, 16, 0, 0)
        iocs_layout.setSpacing(16)

        ioc_sum_sec = DetailSection("IOC Summary", "Extracted indicators of compromise by type.")
        ioc_sum_sec.add_widget(self._ioc_summary_widget)
        iocs_layout.addWidget(ioc_sum_sec)

        ioc_det_sec = DetailSection("IOC Details", "Individual values for selected indicator category.")
        ioc_det_sec.add_widget(self._ioc_details_widget)
        iocs_layout.addWidget(ioc_det_sec)

        iocs_layout.addStretch()

        # Tab 3: Threat Intel
        tab_intel = QWidget()
        intel_layout = QVBoxLayout(tab_intel)
        intel_layout.setContentsMargins(0, 16, 0, 0)
        intel_layout.setSpacing(16)

        threat_sec = DetailSection("Threat Intelligence", "VirusTotal enrichment results.")
        threat_sec.add_widget(self._threat_summary_widget)
        intel_layout.addWidget(threat_sec)

        intel_layout.addStretch()

        # Assemble Tabs
        self._tab_widget.addTab(tab_overview, "Overview & Metrics")
        self._tab_widget.addTab(tab_iocs, "Extracted IOCs")
        self._tab_widget.addTab(tab_intel, "Threat Intelligence")

        layout.addWidget(self._tab_widget)

        # Wrap in Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self._container)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll_area)

    def _connect_signals(self) -> None:
        """
        Connect workspace signals.
        """
        self._ioc_summary_widget.ioc_selected.connect(
            self._ioc_details_widget.display_iocs,
        )

        self._ioc_details_widget.copy_completed.connect(
            self.status_message.emit,
        )

        self._header_card.export_requested.connect(
            self.export_investigation_requested.emit,
        )

        event_bus.investigation_selected.connect(
            self.refresh,
        )

    def _reset_workspace(self) -> None:
        """
        Reset the workspace to its default state.
        """
        self._header_card.reset()
        self._ioc_summary_widget.reset()
        self._ioc_details_widget.reset()
        self._threat_summary_widget.reset()
        self._risk_summary_widget.reset()
        self._metrics_widget.reset()
        self._timeline_widget.reset()

    def load_investigation(self, investigation: Investigation) -> None:
        """
        Display an investigation in the workspace.
        """
        self._header_card.load_investigation(investigation)
        self._ioc_summary_widget.load_investigation(investigation)
        self._ioc_details_widget.reset()
        self._threat_summary_widget.load_investigation(investigation)
        self._risk_summary_widget.load_investigation(investigation)
        self._metrics_widget.load_investigation(investigation)
        self._timeline_widget.load_investigation(investigation)

    def refresh(self) -> None:
        """
        Refresh the workspace using shared application state.
        """
        investigation = ApplicationState.get_current_investigation()

        if investigation is None:
            self._reset_workspace()
            return

        self.load_investigation(investigation)