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

        Fixed hierarchy of rows:

            TOP       Hero + Quick Access        (natural height, no stretch)
            PRIMARY   Investigation Queue + Featured Investigation (stretch 4)
            SECONDARY IOC Distribution + Live Security Events      (stretch 3)
            UTILITY   KPI Section + System Status (natural height, no stretch)

        BATCH 04: layout/geometry is unchanged from Batch 03B -- this
        batch only wires interaction signals, it does not touch
        _build_ui().

        BATCH 03B: Primary/Secondary were previously 3:2. At 1280x720
        that split left Secondary (which carries Live Security Events,
        a row-based feed with real per-row height needs) short on
        absolute pixels, producing the observed row overlap/clipping.
        Moving to 4:3 gives Secondary materially more room while still
        keeping Primary -- the investigation workbench -- the larger
        share, per the stated hierarchy. Root layout spacing is also
        trimmed from MD to SM so more of the page's vertical budget
        goes to content rows instead of inter-row gaps; Hero/Quick
        Access/KPI/System Status keep their own internal margins
        untouched, so this doesn't compress their readability, only
        the dead space between the four stacked rows.

        Hero, Quick Access, KPI Section, and System Status each use
        a (Expanding, Maximum) size policy (see their respective
        widget files) rather than a hard-coded setMaximumHeight()
        pixel value: Maximum means each row can never grow past its
        own natural sizeHint, so it can't take space Primary/
        Secondary need, but it also can't clip its own content.
        """

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN,
        )

        # SM rather than MD: frees vertical budget for the Primary/
        # Secondary content rows, which is where the actual runtime
        # clipping/overlap was observed. The four rows still read as
        # a dense, analyst-workbench composition -- tighter row-to-row
        # rhythm, not tighter content padding within any one row.
        root_layout.setSpacing(Spacing.SM)

        # Header

        root_layout.addWidget(
            self._header_widget
        )

        # --------------------------------------------------
        # TOP: Hero + Quick Access
        # --------------------------------------------------

        top_row = QHBoxLayout()
        top_row.setSpacing(Spacing.LG)

        # BATCH 03B: was 2:1 (Hero favored). Quick Access has three
        # real button labels ("+ Analyze Report", "Browse History",
        # "Threat Intel Lookup") that were being truncated at that
        # width share. Hero's content (wordmark + pulse dot + two
        # badges + clock) compresses far more gracefully than button
        # labels can (a button either fits its label or visibly
        # truncates it), so Quick Access now gets the larger share.
        top_row.addWidget(self._hero_widget, 2)
        top_row.addWidget(self._quick_access, 3)

        root_layout.addLayout(top_row)

        # --------------------------------------------------
        # PRIMARY: Investigation Queue + Featured Investigation
        # --------------------------------------------------

        primary_row = QHBoxLayout()
        primary_row.setSpacing(Spacing.LG)

        # 7:3 -- Queue is the dominant workbench (~70% width), Featured
        # keeps enough width for its metadata block and action button.
        primary_row.addWidget(self._investigation_queue, 7)
        primary_row.addWidget(self._featured_card, 3)

        # BATCH 03B: stretch raised 3 -> 4 (see _build_ui docstring).
        root_layout.addLayout(primary_row, 4)

        # --------------------------------------------------
        # SECONDARY: IOC Distribution + Live Security Events
        # --------------------------------------------------

        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(Spacing.LG)

        secondary_row.addWidget(self._ioc_distribution, 1)
        secondary_row.addWidget(self._live_security_events, 1)

        # BATCH 03B: stretch raised 2 -> 3 (see _build_ui docstring) --
        # this is what gives Live Security Events room to render its
        # rows without overlapping.
        root_layout.addLayout(secondary_row, 3)

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

        # BATCH 04: Investigation Queue row activation (double-click
        # / Enter) and Live Security Events row click both resolve to
        # a real Investigation object and go through the same shared
        # _open_investigation() as the Featured card action -- one
        # "select + navigate" path for every dashboard surface that
        # identifies a concrete investigation, per the architecture
        # rule against parallel selection flows.
        self._investigation_queue.investigation_activated.connect(
            self._open_investigation
        )

        self._live_security_events.investigation_activated.connect(
            self._open_investigation
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

    def _open_investigation(
        self,
        investigation,
    ) -> None:
        """
        Make `investigation` the active investigation and navigate to
        the workspace to view it.

        BATCH 04: single shared implementation of "select + navigate",
        used by the Featured card action, Investigation Queue row
        activation, and Live Security Events row click alike -- so
        there is exactly one place in DashboardPage that performs
        this transition, rather than three copies that could drift.
        Guards against `None` (e.g. a row that no longer exists after
        a race with refresh()) so no caller has to re-check first.
        """

        if investigation is None:
            return

        ApplicationState.select_investigation(
            investigation
        )

        self.navigate_to_page.emit(NavigationPage.WORKSPACE)

    def _open_featured_workspace(
        self,
    ) -> None:
        """
        Open latest investigation.

        Reuses the investigation already fetched by refresh() (and
        currently shown on the Featured card) instead of making a
        second controller/service call for data we already have.
        """

        self._open_investigation(
            self._latest_investigation
        )

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