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
from app.gui.components.feedback.empty_state import EmptyState
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.services.ioc_detail_context import (
    build_investigation_threat_intel_overview,
    build_ioc_detail_context,
)
from app.gui.design.tokens import Spacing
from app.gui.widgets.correlation_widget import CorrelationWidget
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.investigation_header_card import InvestigationHeaderCard
from app.gui.widgets.investigation_metrics_widget import InvestigationMetricsWidget
from app.gui.widgets.investigation_timeline_widget import InvestigationTimelineWidget
from app.gui.widgets.ioc_detail_dialog import IOCDetailDialog
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget
from app.gui.widgets.ioc_summary_widget import IOCSummaryWidget
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.risk_explanation_widget import RiskExplanationWidget
from app.gui.widgets.risk_summary_widget import RiskSummaryWidget
from app.gui.widgets.threat_intelligence_widget import ThreatIntelligenceWidget
from app.logger import logger
from app.services.correlation_models import CorrelationReport
from app.services.correlation_service import CorrelationService
from app.services.risk_explanation_service import RiskExplanationService
from app.settings.service import SettingsService


class InvestigationWorkspacePage(QWidget):
    """
    Main analyst investigation workspace.
    """

    status_message = Signal(str)
    export_investigation_requested = Signal()

    # Tab indices, matching the order tabs are added in `_build_ui()`.
    # Named rather than hardcoded at each call site so navigation
    # (e.g. `_on_threat_intel_requested`) can't silently drift out of
    # sync with the tab order.
    _TAB_OVERVIEW = 0
    _TAB_IOCS = 1
    _TAB_THREAT_INTEL = 2
    _TAB_CORRELATIONS = 3

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

        # Shown instead of the header card + tabs when there is no
        # current investigation (see `refresh()` / `_reset_workspace()`).
        # Reachable both before any investigation has ever been
        # selected and after `ApplicationState.clear_current_investigation()`
        # fires while this page is on screen.
        self._empty_state = EmptyState(
            "No Investigation Selected",
            "Select an investigation from the Dashboard or "
            "Investigation History to view its analyst context here.",
        )

        # Workspace Tabbed Views
        self._tab_widget = QTabWidget()

        # Section Widgets
        self._ioc_summary_widget = IOCSummaryWidget()
        self._ioc_details_widget = IOCDetailsWidget()
        self._threat_summary_widget = ThreatIntelligenceWidget()
        self._risk_summary_widget = RiskSummaryWidget()
        self._metrics_widget = InvestigationMetricsWidget()
        self._timeline_widget = InvestigationTimelineWidget()
        self._correlation_widget = CorrelationWidget()
        self._risk_explanation_widget = RiskExplanationWidget()

        # Framework-independent correlation service: derives
        # deterministic relationships between evidence already
        # present in the current investigation. The GUI consumes
        # this service rather than calculating correlations itself
        # (see PHASE3_PART3B section 6/7).
        self._correlation_service = CorrelationService()

        # Framework-independent risk explanation service: derives
        # "why this risk?" context from the investigation's
        # existing, already-persisted risk assessment, evidence,
        # threat intelligence, and correlations. Never recalculates
        # the score/severity itself (see PHASE3C-1/PHASE3C-2
        # section 3: "the GUI must NOT calculate risk").
        self._risk_explanation_service = RiskExplanationService()

        # Maps SHA256 hash -> enriched threat-intelligence record for
        # the investigation currently on display. Rebuilt on every
        # `load_investigation()` and handed to `_ioc_details_widget`
        # so the "Extracted IOCs" tab can show, per hash, whether it
        # was enriched and what the verdict was -- without the GUI
        # re-deriving or duplicating anything `ThreatIntelService`
        # already computed.
        self._threat_intel_by_value: dict[str, dict] = {}

        # The investigation currently on display, kept so the IOC
        # detail flow (`_on_ioc_detail_requested`) can build full
        # investigation context for a single selected IOC without
        # re-fetching it. `None` when the workspace is empty.
        self._investigation: Investigation | None = None

        self._settings_service = SettingsService()

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

        # 1b. Empty state, shown instead of the header card + tabs
        # when there is no current investigation.
        layout.addWidget(self._empty_state)

        # 2. Build Tab Pages
        tab_overview = QWidget()
        overview_layout = QVBoxLayout(tab_overview)
        overview_layout.setContentsMargins(0, Spacing.LG, 0, 0)
        overview_layout.setSpacing(Spacing.LG)

        risk_sec = DetailSection("Risk Assessment", "Overall investigation risk posture.")
        risk_sec.add_widget(self._risk_summary_widget)
        overview_layout.addWidget(risk_sec)

        risk_explanation_sec = DetailSection(
            "Why This Risk?",
            "Contributing evidence, threat intelligence, and "
            "correlation context behind the score above.",
        )
        risk_explanation_sec.add_widget(self._risk_explanation_widget)
        overview_layout.addWidget(risk_explanation_sec)

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
        iocs_layout.setContentsMargins(0, Spacing.LG, 0, 0)
        iocs_layout.setSpacing(Spacing.LG)

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
        intel_layout.setContentsMargins(0, Spacing.LG, 0, 0)
        intel_layout.setSpacing(Spacing.LG)

        threat_sec = DetailSection("Threat Intelligence", "VirusTotal enrichment results.")
        threat_sec.add_widget(self._threat_summary_widget)
        intel_layout.addWidget(threat_sec)

        intel_layout.addStretch()

        # Tab 4: Correlations
        tab_correlations = QWidget()
        correlations_layout = QVBoxLayout(tab_correlations)
        correlations_layout.setContentsMargins(0, Spacing.LG, 0, 0)
        correlations_layout.setSpacing(Spacing.LG)

        correlation_sec = DetailSection(
            "Evidence Correlations",
            "Deterministic relationships between evidence already "
            "extracted for this investigation.",
        )
        correlation_sec.add_widget(self._correlation_widget)
        correlations_layout.addWidget(correlation_sec)

        correlations_layout.addStretch()

        # Assemble Tabs
        self._tab_widget.addTab(tab_overview, "Overview & Metrics")
        self._tab_widget.addTab(tab_iocs, "Extracted IOCs")
        self._tab_widget.addTab(tab_intel, "Threat Intelligence")
        self._tab_widget.addTab(tab_correlations, "Correlations")

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
            self._on_ioc_selected,
        )

        self._ioc_details_widget.threat_intel_requested.connect(
            self._on_threat_intel_requested,
        )

        self._ioc_details_widget.ioc_detail_requested.connect(
            self._on_ioc_detail_requested,
        )

        self._ioc_details_widget.copy_completed.connect(
            self.status_message.emit,
        )

        self._header_card.export_requested.connect(
            self.export_investigation_requested.emit,
        )

        self._risk_explanation_widget.evidence_category_selected.connect(
            self._on_risk_evidence_category_selected,
        )

        self._risk_explanation_widget.correlation_view_requested.connect(
            self._on_risk_correlation_view_requested,
        )

        event_bus.investigation_selected.connect(
            self.refresh,
        )

    def _reset_workspace(self) -> None:
        """
        Reset the workspace to its default state.
        """
        self._threat_intel_by_value = {}
        self._investigation = None
        self._header_card.reset()
        self._ioc_summary_widget.reset()
        self._ioc_details_widget.reset()
        self._threat_summary_widget.reset()
        self._risk_summary_widget.reset()
        self._metrics_widget.reset()
        self._timeline_widget.reset()
        self._correlation_widget.reset()
        self._risk_explanation_widget.reset()

        self._header_card.setVisible(False)
        self._tab_widget.setVisible(False)
        self._empty_state.setVisible(True)

    def load_investigation(self, investigation: Investigation) -> None:
        """
        Display an investigation in the workspace.
        """
        self._investigation = investigation

        self._threat_intel_by_value = {}
        ti = investigation.threat_intelligence or {}

        for record in ti.get("hashes", []):
            if record.get("sha256"):
                self._threat_intel_by_value[record["sha256"]] = record

        for record in ti.get("ips", []):
            if record.get("ip"):
                self._threat_intel_by_value[record["ip"]] = record

        for record in ti.get("domains", []):
            if record.get("domain"):
                self._threat_intel_by_value[record["domain"]] = record

        for record in ti.get("urls", []):
            if record.get("url"):
                self._threat_intel_by_value[record["url"]] = record

        settings = self._settings_service.load_settings()

        threat_intel_overview = build_investigation_threat_intel_overview(
            investigation,
            api_key_configured=bool(settings.virustotal_api_key),
        )

        self._header_card.load_investigation(
            investigation,
            threat_intel_overview,
        )
        self._ioc_summary_widget.load_investigation(
            investigation,
            threat_intel_overview,
        )
        self._ioc_details_widget.reset()
        self._threat_summary_widget.load_investigation(
            investigation,
            threat_intel_overview,
        )
        self._risk_summary_widget.load_investigation(investigation)
        self._metrics_widget.load_investigation(investigation)
        self._timeline_widget.load_investigation(investigation)

        correlation_report = self._correlation_service.correlate(investigation)
        self._correlation_widget.load_report(correlation_report)

        self._load_risk_explanation(
            investigation,
            correlation_report,
            api_key_configured=bool(settings.virustotal_api_key),
        )

        self._empty_state.setVisible(False)
        self._header_card.setVisible(True)
        self._tab_widget.setVisible(True)

    def _load_risk_explanation(
        self,
        investigation: Investigation,
        correlation_report: CorrelationReport,
        api_key_configured: bool,
    ) -> None:
        """
        Build and display the "why this risk?" explanation for the
        investigation currently loading.

        `RiskExplanationService.explain()` is deterministic and
        read-only (see PHASE3C-1), but service failures must never
        crash the workspace or expose a raw exception to the
        analyst (see PHASE3C-2 section 10) -- a failed explanation
        still leaves the existing risk score/severity above it
        fully intact and correct.
        """

        try:
            explanation = self._risk_explanation_service.explain(
                investigation,
                correlation_report=correlation_report,
                api_key_configured=api_key_configured,
            )

        except Exception:
            logger.exception(
                "Failed to build risk explanation for investigation "
                "%r.",
                investigation.investigation_id,
            )

            self._risk_explanation_widget.show_error()

            return

        self._risk_explanation_widget.load_explanation(explanation)

    def _on_risk_evidence_category_selected(self, ioc_type: str) -> None:
        """
        Jump from the risk explanation's evidence breakdown to that
        IOC category's details, completing the "Risk explanation ->
        Contributing IOC -> IOC context" drill-down (see PHASE3C-2
        section 5).
        """

        self._tab_widget.setCurrentIndex(self._TAB_IOCS)

        self._ioc_summary_widget.select_category(ioc_type)

    def _on_risk_correlation_view_requested(self) -> None:
        """
        Jump from the risk explanation's correlation summary to the
        Correlations tab, completing the "Risk explanation ->
        Correlation -> Related evidence" drill-down (see PHASE3C-2
        section 5).
        """

        self._tab_widget.setCurrentIndex(self._TAB_CORRELATIONS)

    def _on_ioc_selected(self, ioc_type: str, values: list[str]) -> None:
        """
        Display the selected IOC category, attaching threat-
        intelligence context for categories that have it.

        All four Phase 3E categories (SHA256, IPv4, domains, URLs)
        carry threat-intelligence enrichment (see
        `ThreatIntelService`); any other category is shown exactly
        as before, with the Threat Intel column hidden.
        """
        threat_intel_lookup = (
            self._threat_intel_by_value if ioc_type in {"sha256", "ipv4", "domains", "urls"} else None
        )

        self._ioc_details_widget.display_iocs(
            ioc_type,
            values,
            threat_intel_lookup,
        )

    def _on_ioc_detail_requested(self, ioc_type: str, value: str) -> None:
        """
        Open the IOC detail dialog for a single selected indicator.

        Builds context via `build_ioc_detail_context()` (investigation
        context, risk significance, honest threat-intelligence
        status) and records the selection on `ApplicationState` so
        the rest of the app can see which specific IOC the analyst
        is currently drilled into.
        """

        if self._investigation is None:
            # Shouldn't normally happen -- the IOC details table is
            # only populated while an investigation is loaded -- but
            # guard against a stale signal arriving after the
            # workspace was reset.
            self.status_message.emit(
                "No investigation is currently loaded.",
            )
            return

        ApplicationState.set_selected_ioc(ioc_type, value)

        settings = self._settings_service.load_settings()

        context = build_ioc_detail_context(
            self._investigation,
            ioc_type,
            value,
            self._threat_intel_by_value,
            api_key_configured=bool(settings.virustotal_api_key),
        )

        dialog = IOCDetailDialog(context, parent=self)

        dialog.threat_intel_requested.connect(
            self._on_threat_intel_requested,
        )

        dialog.exec()

    def _on_threat_intel_requested(self, value: str) -> None:
        """
        Jump from an enriched IOC to its threat-intelligence record.

        Completes the "Investigation -> IOC -> Threat Intelligence"
        drill-down: switches to the Threat Intelligence tab and
        focuses the matching row, reusing the existing enrichment
        table rather than opening a second view of the same data.
        """
        self._tab_widget.setCurrentIndex(self._TAB_THREAT_INTEL)

        found = self._threat_summary_widget.select_indicator(value)

        if not found:
            self.status_message.emit(
                "That indicator's threat-intelligence record is no "
                "longer available.",
            )

    def refresh(self) -> None:
        """
        Refresh the workspace using shared application state.
        """
        investigation = ApplicationState.get_current_investigation()

        if investigation is None:
            self._reset_workspace()
            return

        self.load_investigation(investigation)
