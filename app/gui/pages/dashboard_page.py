"""
Dashboard page for the SOC-IQ desktop application.

Functions as an Executive Command Center Landing Page, presenting situational
awareness, key security metrics, threat status, and direct action triggers.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
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

# ThreatIntelligenceFeedWidget is intentionally NOT imported here.
# It has been confirmed (Batch 3 audit) to be a relabeled rendering
# of the same recent-investigation data already shown in the
# Investigation Queue / Featured Investigation, so it has been
# removed from the dashboard layout. The widget file itself and its
# backing service are untouched -- only its dashboard usage is gone.


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

        # Populated by refresh() from the same get_recent_investigations()
        # call used for the Investigation Queue, so _open_featured_workspace()
        # never has to make a second controller round-trip just to get the
        # investigation the Featured card is already showing.
        self._latest_investigation = None

        self._toast_box = QVBoxLayout()

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self._header_widget = PageHeader(
            title="SOC-IQ Cyber Operations Center",
            subtitle="Live threat status and investigation overview.",
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

        No page-level QScrollArea. Instead of the previous flat 3x2
        equal-weight grid (which gave a utility widget like System
        Status the same visual weight as the Investigation Queue,
        and needed a page-level scroll area to fit), the dashboard
        is built as a fixed hierarchy of rows:

            TOP       Hero + Quick Access        (natural height, no stretch)
            PRIMARY   Investigation Queue + Featured Investigation (stretch 3)
            SECONDARY IOC Distribution + Live Security Events      (stretch 2)
            UTILITY   KPI Section + System Status (natural height, no stretch)

        Hero, Quick Access, KPI Section, and System Status each use
        a (Expanding, Maximum) size policy (see their respective
        widget files) rather than a hard-coded setMaximumHeight()
        pixel value: Maximum means each row can never grow past its
        own natural sizeHint (driven by real font/badge/button
        sizes), so it can't expand to take space Primary/Secondary
        need, but it also can't clip its own content the way a
        fixed pixel guess did in the previous pass -- that guess is
        what clipped the KPI cards, cramped the Featured card, and
        caused overlapping Live Events rows, because nothing
        adapted the cap when real content needed more room than the
        guess allowed. The Investigation Queue and Live Security
        Events widgets are unchanged and keep whatever internal/
        table scrolling they already had.
        """

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
        )

        root_layout.setSpacing(Spacing.LG)

        # Header

        root_layout.addWidget(
            self._header_widget
        )

        # --------------------------------------------------
        # TOP: Hero + Quick Access
        # --------------------------------------------------

        top_row = QHBoxLayout()
        top_row.setSpacing(Spacing.LG)

        # 2:1 rather than a more hero-heavy split -- Quick Access
        # has three real buttons to fit ("+ Analyze Report",
        # "Browse History", "Threat Intel Lookup") while the Hero
        # strip's content (label + pulse dot + two badges + clock)
        # compresses more gracefully, so Quick Access needs the
        # larger share of the narrow-width safety margin.
        top_row.addWidget(self._hero_widget, 2)
        top_row.addWidget(self._quick_access, 1)

        root_layout.addLayout(top_row)

        # --------------------------------------------------
        # PRIMARY: Investigation Queue + Featured Investigation
        # --------------------------------------------------

        primary_row = QHBoxLayout()
        primary_row.setSpacing(Spacing.LG)

        primary_row.addWidget(self._investigation_queue, 5)
        primary_row.addWidget(self._featured_card, 2)

        # Highest layout priority per the target hierarchy
        # (investigations are the primary analyst workspace).
        # Hero/Quick Access above and KPI/System Status below now
        # size themselves to their own natural content height
        # (Expanding/Maximum size policy, no stretch factor here),
        # so all real extra vertical space is free to go to this
        # row and the Secondary row below -- this is what gives
        # Featured Investigation's "Open Workspace" button room to
        # render uncompressed instead of being pushed off the
        # bottom of an undersized row.
        root_layout.addLayout(primary_row, 3)

        # --------------------------------------------------
        # SECONDARY: IOC Distribution + Live Security Events
        # --------------------------------------------------

        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(Spacing.LG)

        secondary_row.addWidget(self._ioc_distribution, 1)
        secondary_row.addWidget(self._live_security_events, 1)

        # Second-highest priority -- enough of its own stretch
        # share that Live Security Events has room to render its
        # visible rows without overlapping, without taking that
        # room away from Primary.
        root_layout.addLayout(secondary_row, 2)

        # --------------------------------------------------
        # UTILITY: KPI Section + System Status
        # --------------------------------------------------

        utility_row = QHBoxLayout()
        utility_row.setSpacing(Spacing.LG)

        utility_row.addWidget(self._kpi_section, 3)
        utility_row.addWidget(self._system_status_section, 1)

        root_layout.addLayout(utility_row)

        root_layout.addLayout(self._toast_box)

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

        Reuses the investigation already fetched by refresh() (and
        currently shown on the Featured card) instead of making a
        second controller/service call for data we already have.
        """

        latest = self._latest_investigation

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
        #
        # get_latest_investigation() is intentionally not called here:
        # recent[0] is the same investigation it would return, so deriving
        # it from the recent-investigations fetch avoids a redundant
        # controller round-trip. get_threat_feed() is also gone -- the
        # dashboard no longer renders the Threat Intelligence Feed widget.
        try:
            threat_level, badge = self._controller.get_threat_status()
            summary = self._controller.get_summary()
            recent = self._controller.get_recent_investigations(limit=10)
            distribution = self._controller.get_ioc_distribution()
            status = self._controller.get_system_status()
        except Exception as error:
            self._show_toast(
                f"Dashboard data could not be refreshed: {error}",
                ToastType.ERROR,
            )
            return

        latest = recent[0] if recent else None

        # Stored so _open_featured_workspace() can reuse it rather than
        # querying the controller again.
        self._latest_investigation = latest

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

        self._system_status_section.load_status(status)

        self._hero_widget.update_timestamp()