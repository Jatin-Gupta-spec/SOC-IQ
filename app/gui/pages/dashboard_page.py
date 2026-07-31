"""
Dashboard page for the SOC-IQ desktop application.

Functions as an Executive Command Center Landing Page, presenting situational
awareness, key security metrics, threat status, and direct action triggers.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.layout.page_header import PageHeader
from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.design.tokens import Spacing
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.widgets.dashboard.dashboard_hero_widget import DashboardHeroWidget
from app.gui.widgets.dashboard.featured_investigation_card import (
    FeaturedInvestigationCard,
)
from app.gui.components.timeline.timeline_widget import (
    TimelineWidget,
    TimelineEvent,
)
from app.gui.widgets.dashboard.kpi_section import KPISection
from app.gui.widgets.dashboard.quick_access_widget import QuickAccessWidget


class DashboardPage(QWidget):
    """
    Command Center Dashboard Landing Page.
    """

    navigate_to_page = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._controller = DashboardController()

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self._header_widget = PageHeader(
            title="SOC-IQ Cyber Operations Center",
            subtitle=(
                "Situational awareness, key threat metrics, "
                "and executive investigation overview."
            ),
        )

        # --------------------------------------------------
        # Dashboard Widgets
        # --------------------------------------------------

        self._hero_widget = DashboardHeroWidget()

        self._kpi_section = KPISection()

        self._featured_card = (
            FeaturedInvestigationCard()
        )

        self._timeline = TimelineWidget()

        self._quick_access = (
            QuickAccessWidget()
        )

        self._system_status_card = (
            ModernCard()
        )

        self._build_ui()

        self._connect_signals()

        self.refresh()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Construct dashboard layout.
        """

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        root_layout.setSpacing(24)

        # Header

        root_layout.addWidget(
            self._header_widget
        )

        # Hero Banner

        root_layout.addWidget(
            self._hero_widget
        )

        # KPI Cards

        root_layout.addWidget(
            self._kpi_section
        )

        # Main Content

        columns_layout = QHBoxLayout()

        columns_layout.setSpacing(24)

        # Left Column

        left_column = QVBoxLayout()

        left_column.setSpacing(24)

        left_column.addWidget(
            self._featured_card
        )

        left_column.addStretch()

        # Right Column

        right_column = QVBoxLayout()

        right_column.setSpacing(24)

        right_column.addWidget(
            self._timeline,
            1,
        )

        self._build_system_status_card()

        right_column.addWidget(
            self._system_status_card
        )

        right_column.addStretch()

        columns_layout.addLayout(
            left_column,
            3,
        )

        columns_layout.addLayout(
            right_column,
            2,
        )

        root_layout.addLayout(
            columns_layout
        )

        root_layout.addStretch()

    # --------------------------------------------------
    # System Card
    # --------------------------------------------------

    def _build_system_status_card(
        self,
    ) -> None:
        """
        Build infrastructure health card.
        """

        palette = (
            self._system_status_card.theme.palette
        )

        fonts = (
            self._system_status_card.theme.fonts
        )

        status = self._controller.get_system_status()

        card_layout = QVBoxLayout()

        card_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        card_layout.setSpacing(
            Spacing.MD,
        )

        title = QLabel(
            "System & Infrastructure Health"
        )

        title.setFont(
            fonts.title()
        )

        title.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 600;
            """
        )

        self._db_status = QLabel()

        self._db_status.setFont(fonts.body())

        self._db_status.setStyleSheet(
            f"color: {palette.success};"
        )

        self._vt_status = QLabel()

        self._vt_status.setFont(fonts.body())

        self._vt_status.setStyleSheet(
            f"color: {palette.info};"
        )

        self._engine_status = QLabel()

        self._engine_status.setFont(fonts.body())

        self._engine_status.setStyleSheet(
            f"""
            color:
            {palette.text_secondary};
            """
        )

        card_layout.addWidget(title)
        card_layout.addWidget(self._db_status)
        card_layout.addWidget(self._vt_status)
        card_layout.addWidget(self._engine_status)

        self._system_status_card.add_layout(
            card_layout
        )

    # --------------------------------------------------
    # Signals
    # --------------------------------------------------

    def _connect_signals(
        self,
    ) -> None:
        """
        Connect dashboard signals.
        """

        event_bus.investigation_selected.connect(
            self.refresh
        )

        event_bus.investigation_created.connect(
            self.refresh
        )

        self._featured_card.open_workspace_requested.connect(
            self._open_featured_workspace
        )

        self._quick_access.navigate_to_analyze.connect(
            lambda: self.navigate_to_page.emit(1)
        )

        self._quick_access.navigate_to_history.connect(
            lambda: self.navigate_to_page.emit(5)
        )

        self._quick_access.navigate_to_threat_intel.connect(
            lambda: self.navigate_to_page.emit(3)
        )

    # --------------------------------------------------
    # Navigation
    # --------------------------------------------------

    def _open_featured_workspace(
        self,
    ) -> None:
        """
        Open latest investigation.
        """

        latest = (
            self._controller
            .get_latest_investigation()
        )

        if latest is None:
            return

        ApplicationState.select_investigation(
            latest
        )

        self.navigate_to_page.emit(7)

    # --------------------------------------------------
    # Refresh
    # --------------------------------------------------

    def refresh(
        self,
    ) -> None:
        """
        Refresh dashboard.
        """

        self._hero_widget.update_timestamp()

        threat_level, badge = (
            self._controller.get_threat_status()
        )

        self._hero_widget.set_threat_level(
            threat_level,
            badge,
        )

        summary = (
            self._controller.get_summary()
        )

        self._kpi_section.set_metrics(
            reports=str(summary["reports"]),
            iocs=str(summary["iocs"]),
            high_risk=str(summary["high_risk"]),
            database=str(summary["database"]),
        )

        latest = (
            self._controller.get_latest_investigation()
        )

        self._featured_card.load_investigation(
            latest
        )

        status = self._controller.get_system_status()

        self._db_status.setText(
            f"• SQLite Database : {status['database']}"
        )

        self._vt_status.setText(
            f"• VirusTotal API : {status['virustotal']}"
        )

        self._engine_status.setText(
            f"• Analysis Engine : {status['analysis_engine']}"
        )

        self._timeline.clear()

        for event in self._controller.get_dashboard_timeline():
            self._timeline.add_event(event)