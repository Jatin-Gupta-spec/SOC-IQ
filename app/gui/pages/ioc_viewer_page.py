"""
IOC Viewer Page for the SOC-IQ desktop application.

Provides indicator search, category aggregation, and detailed IOC inspection
across all recorded investigations.
"""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.gui.components.layout.component_section import ComponentSection
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget
from app.gui.widgets.ioc_summary_widget import IOCSummaryWidget
from app.gui.widgets.page_container import PageContainer


class IOCViewerPage(QWidget):
    """
    Indicators of Compromise (IOC) Viewer Page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._container = PageContainer(
            title="IOC Explorer & Repository",
            description=(
                "Browse and inspect indicators of compromise (IPs, Domains, Hashes, "
                "URLs, File Paths) extracted across all investigations."
            ),
        )

        self._ioc_summary = IOCSummaryWidget()
        self._ioc_details = IOCDetailsWidget()

        # Tracks which investigation is currently rendered so refresh()
        # can tell a genuine change apart from a redundant signal.
        self._loaded_investigation_id: object | None = None

        self._build_ui()
        self._connect_signals()

        self.refresh()

    def _build_ui(self) -> None:
        """
        Build IOC Viewer user interface.
        """
        layout = self._container.content_layout()

        # IOC Summary Section
        sum_section = ComponentSection(
            title="Extracted Indicators Summary",
            description="Categorized indicator breakdown for current investigation.",
        )
        sum_section.add_widget(self._ioc_summary)
        layout.addWidget(sum_section)

        # IOC Details Section
        det_section = ComponentSection(
            title="Indicator Value Explorer",
            description="Select an indicator type above to view full string values and copy to clipboard.",
        )
        det_section.add_widget(self._ioc_details)
        layout.addWidget(det_section)

        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

    def _connect_signals(self) -> None:
        """
        Connect widget signals.
        """
        self._ioc_summary.ioc_selected.connect(
            self._ioc_details.display_iocs,
        )

        # Previously this page only refreshed on
        # `investigation_selected`. That means if the
        # investigation currently open in the IOC Viewer is
        # later edited or deleted (e.g. from the History
        # page), this page kept showing stale — or, for a
        # deleted investigation, entirely orphaned — IOC
        # data with nothing to indicate the underlying
        # record no longer matches reality. `refresh()`
        # already re-reads from `ApplicationState` and
        # safely no-ops when nothing relevant changed, so
        # wiring these in is a safe, low-cost correctness fix.
        event_bus.investigation_selected.connect(self.refresh)
        event_bus.investigation_updated.connect(self.refresh)
        event_bus.investigation_removed.connect(self.refresh)

    def cleanup(self) -> None:
        """
        Disconnect this page's `event_bus` subscriptions.

        `event_bus` is a long-lived, application-wide singleton.
        Without an explicit disconnect, its connections keep this
        page's `refresh` slot registered for the lifetime of the
        app even after the page itself is torn down — leaking the
        page (and everything it holds) and risking a `RuntimeError`
        the next time an event fires against an already-deleted
        widget. Safe to call more than once; the container/window
        that owns this page should call it when the page is
        removed or the app is shutting down.
        """

        for signal in (
            event_bus.investigation_selected,
            event_bus.investigation_updated,
            event_bus.investigation_removed,
        ):
            try:
                signal.disconnect(self.refresh)
            except (RuntimeError, TypeError):
                # Already disconnected, or the signal/slot is gone.
                pass

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Ensure cleanup runs if this page is ever used as (or
        inside) a top-level window that receives a close event.
        """

        self.cleanup()
        super().closeEvent(event)

    def refresh(self) -> None:
        """
        Refresh page content using current investigation.
        """
        investigation = ApplicationState.get_current_investigation()

        if investigation is None:
            if self._loaded_investigation_id is None:
                # Already showing the empty state -- nothing changed.
                return

            self._ioc_summary.reset()
            self._ioc_details.reset()
            self._loaded_investigation_id = None
            return

        same_investigation = investigation.id == self._loaded_investigation_id

        self._ioc_summary.load_investigation(investigation)

        if not same_investigation:
            # Only clear the detail pane when switching to a
            # genuinely different investigation. Re-selecting the
            # same investigation, or an `investigation_updated`
            # refresh for it, would otherwise wipe out whatever IOC
            # category/value the analyst already had open for no
            # reason.
            self._ioc_details.reset()

        self._loaded_investigation_id = investigation.id