"""
Dashboard page for the SOC-IQ desktop application.

Functions as an Executive Command Center Landing Page, presenting situational
awareness, key security metrics, threat status, and direct action triggers.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.feedback.toast_notification import (
    ToastNotification,
    ToastType,
)
from app.gui.components.layout.page_header import PageHeader
from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.design.tokens import Spacing
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.widgets.dashboard.dashboard_hero_widget import DashboardHeroWidget
from app.gui.widgets.dashboard.featured_investigation_card import (
    FeaturedInvestigationCard,
)
from app.gui.widgets.dashboard.investigation_queue_widget import (
    InvestigationQueueWidget,
)
from app.gui.widgets.dashboard.threat_intelligence_feed_widget import (
    ThreatIntelligenceFeedWidget,
)
from app.gui.widgets.dashboard.ioc_distribution_widget import (
    IOCDistributionWidget,
)
from app.gui.widgets.dashboard.kpi_section import KPISection
from app.gui.widgets.dashboard.live_security_events_widget import (
    LiveSecurityEventsWidget,
)
from app.gui.widgets.dashboard.quick_access_widget import QuickAccessWidget
from app.gui.widgets.dashboard.system_status_section import SystemStatusSection
from app.gui.widgets.sidebar import NavigationPage


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

        self._toast_box = QVBoxLayout()

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

        self._investigation_queue = (
            InvestigationQueueWidget()
        )

        self._ioc_distribution = (
            IOCDistributionWidget()
        )

        self._threat_feed = (
            ThreatIntelligenceFeedWidget()
        )

        self._featured_card = (
            FeaturedInvestigationCard()
        )

        self._quick_access = (
            QuickAccessWidget()
        )

        self._system_status_section = (
            SystemStatusSection()
        )

        self._live_security_events = (
            LiveSecurityEventsWidget()
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

        The page is placed directly inside the app's top-level
        `QStackedWidget` (see `main_window.py`), which never
        scrolls its pages itself -- it only ever gives a page
        exactly the viewport's size. `InvestigationWorkspacePage`
        (the other long page hung off the same stack) accounts for
        this by wrapping its content in a `QScrollArea`; this page
        previously didn't, so once the header, hero, KPI row, and
        three-row workbench grid combined exceeded the viewport
        height, the grid's bottom row had nowhere to go and was cut
        off/squeezed instead of becoming reachable by scrolling.
        Wrapping the same content in a `QScrollArea` here brings the
        page in line with that established pattern.
        """

        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        content_layout.setSpacing(24)

        # Header

        content_layout.addWidget(
            self._header_widget
        )

        # Hero Banner

        content_layout.addWidget(
            self._hero_widget
        )

        # KPI Cards

        content_layout.addWidget(
            self._kpi_section
        )

        # Quick Access
        #
        # Previously created in __init__ but never added to any
        # layout, so it never appeared and its navigate_to_*
        # signals (wired in _connect_signals) had no way to fire.

        content_layout.addWidget(
            self._quick_access
        )

        # --------------------------------------------------
        # SOC Workbench
        # --------------------------------------------------

        grid = QGridLayout()

        grid.setHorizontalSpacing(Spacing.LG)
        grid.setVerticalSpacing(Spacing.LG)

        grid.addWidget(
            self._investigation_queue,
            0,
            0,
        )

        grid.addWidget(
            self._threat_feed,
            0,
            1,
        )

        grid.addWidget(
            self._ioc_distribution,
            1,
            0,
        )

        grid.addWidget(
            self._live_security_events,
            1,
            1,
        )

        grid.addWidget(
            self._featured_card,
            2,
            0,
        )

        grid.addWidget(
            self._system_status_section,
            2,
            1,
        )

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        content_layout.addLayout(grid)

        content_layout.addLayout(self._toast_box)

        content_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(content)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll_area)

    # --------------------------------------------------
    # Feedback
    # --------------------------------------------------

    def _show_toast(self, message: str, toast_type: ToastType) -> None:
        """
        Display an ephemeral toast notification.
        """
        while self._toast_box.count():
            child = self._toast_box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        toast = ToastNotification(message, toast_type)
        self._toast_box.addWidget(toast)

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
            lambda: self.navigate_to_page.emit(NavigationPage.ANALYZE)
        )

        self._quick_access.navigate_to_history.connect(
            lambda: self.navigate_to_page.emit(NavigationPage.HISTORY)
        )

        self._quick_access.navigate_to_threat_intel.connect(
            lambda: self.navigate_to_page.emit(
                NavigationPage.THREAT_INTELLIGENCE
            )
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

        try:
            latest = (
                self._controller
                .get_latest_investigation()
            )
        except Exception as error:
            self._show_toast(
                f"Could not open the latest investigation: {error}",
                ToastType.ERROR,
            )
            return

        if latest is None:
            return

        ApplicationState.select_investigation(
            latest
        )

        self.navigate_to_page.emit(NavigationPage.WORKSPACE)

    # --------------------------------------------------
    # Refresh
    # --------------------------------------------------

    def refresh(
        self,
    ) -> None:
        """
        Refresh dashboard.
        """

        # Fetch everything first, before touching any widget. If any single
        # controller call fails (e.g. database unavailable), we must not
        # apply a partial update: that would leave some widgets showing
        # fresh data and others showing stale data with no indication
        # anything went wrong, and could misrepresent a data-access failure
        # as "no data" once individual widgets are updated with empty
        # results.
        try:
            threat_level, badge = self._controller.get_threat_status()
            summary = self._controller.get_summary()
            latest = self._controller.get_latest_investigation()
            recent = self._controller.get_recent_investigations(limit=10)
            distribution = self._controller.get_ioc_distribution()
            feed = self._controller.get_threat_feed(limit=10)
            status = self._controller.get_system_status()
        except Exception as error:
            self._show_toast(
                f"Dashboard data could not be refreshed: {error}",
                ToastType.ERROR,
            )
            return

        self._hero_widget.set_threat_level(
            threat_level,
            badge,
        )

        self._kpi_section.set_metrics(
            reports=str(summary["reports"]),
            iocs=str(summary["iocs"]),
            high_risk=str(summary["high_risk"]),
            database=str(summary["database"]),
        )

        self._featured_card.load_investigation(
            latest
        )

        self._investigation_queue.load_investigations(
            recent
        )

        self._ioc_distribution.load_distribution(
            distribution
        )

        self._threat_feed.load_feed(
            feed
        )

        self._system_status_section.load_status(status)

        self._hero_widget.update_timestamp()