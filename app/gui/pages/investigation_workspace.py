"""
Investigation workspace page for the SOC-IQ desktop application.

This page provides the primary analyst workspace used to
review completed investigations.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.events.application_state import (
    ApplicationState,
)
from app.gui.events.event_bus import (
    event_bus,
)
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.investigation_header_card import (
    InvestigationHeaderCard,
)
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.ioc_summary_widget import (
    IOCSummaryWidget,
)
from app.gui.widgets.ioc_details_widget import (
    IOCDetailsWidget,
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

    status_message = Signal(
        str,
    )

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
        # Investigation Header
        # ------------------------------------------

        self._header_card = (
            InvestigationHeaderCard()
        )

        # ------------------------------------------
        # Section Widgets
        # ------------------------------------------

        self._ioc_summary_widget = (
            IOCSummaryWidget()
        )

        self._ioc_details_widget = (
            IOCDetailsWidget()
        )

        self._threat_summary_widget = (
            ThreatIntelligenceWidget()
        )

        self._risk_summary_widget = (
            RiskSummaryWidget()
        )

        self._build_ui()

        self._ioc_summary_widget.ioc_selected.connect(
            self._ioc_details_widget.display_iocs,
        )

        self._ioc_details_widget.copy_completed.connect(
            self.status_message.emit,
        )

        event_bus.investigation_selected.connect(
            self.refresh,
        )

        self.refresh()

    def _build_ui(self) -> None:
        """
        Build the workspace layout.
        """

        layout = self._container.content_layout()

        # --------------------------------------------------
        # Investigation Header
        # --------------------------------------------------

        layout.addWidget(
            self._header_card,
        )

        # --------------------------------------------------
        # IOC Summary
        # --------------------------------------------------

        ioc_section = DetailSection(
            "IOC Summary",
            "Extracted indicators of compromise.",
        )

        ioc_section.add_widget(
            self._ioc_summary_widget,
        )

        layout.addWidget(
            ioc_section,
        )

        # --------------------------------------------------
        # IOC Details
        # --------------------------------------------------

        ioc_details_section = DetailSection(
            "IOC Details",
            "Individual IOC values for the selected IOC type.",
        )

        ioc_details_section.add_widget(
            self._ioc_details_widget,
        )

        layout.addWidget(
            ioc_details_section,
        )

        # --------------------------------------------------
        # Threat Intelligence
        # --------------------------------------------------

        threat_section = DetailSection(
            "Threat Intelligence",
            "VirusTotal enrichment results.",
        )

        threat_section.add_widget(
            self._threat_summary_widget,
        )

        layout.addWidget(
            threat_section,
        )

        # --------------------------------------------------
        # Risk Assessment
        # --------------------------------------------------

        risk_section = DetailSection(
            "Risk Assessment",
            "Overall investigation risk.",
        )

        risk_section.add_widget(
            self._risk_summary_widget,
        )

        layout.addWidget(
            risk_section,
        )

        layout.addStretch()

        # --------------------------------------------------
        # Scroll Area
        # --------------------------------------------------

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(
            True,
        )

        scroll_area.setFrameShape(
            QFrame.Shape.NoFrame,
        )

        scroll_area.setWidget(
            self._container,
        )

        root_layout = QVBoxLayout()

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.addWidget(
            scroll_area,
        )

        self.setLayout(
            root_layout,
        )

    def _reset_workspace(
        self,
    ) -> None:
        """
        Reset the workspace to its default state.
        """

        self._header_card.reset()

        self._ioc_summary_widget.reset()

        self._ioc_details_widget.reset()

        self._threat_summary_widget.reset()

        self._risk_summary_widget.reset()

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display an investigation in the workspace.
        """

        self._header_card.load_investigation(
            investigation,
        )

        self._ioc_summary_widget.load_investigation(
            investigation,
        )

        self._ioc_details_widget.reset()

        self._threat_summary_widget.load_investigation(
            investigation,
        )

        self._risk_summary_widget.load_investigation(
            investigation,
        )

    def refresh(
        self,
    ) -> None:
        """
        Refresh the workspace using the shared
        application state.
        """

        investigation = (
            ApplicationState.get_current_investigation()
        )

        if investigation is None:

            self._reset_workspace()

            return

        self.load_investigation(
            investigation,
        )