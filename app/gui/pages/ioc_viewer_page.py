"""
IOC Viewer Page for the SOC-IQ desktop application.

Provides indicator search, category aggregation, and detailed IOC inspection
across all recorded investigations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
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

        event_bus.investigation_selected.connect(self.refresh)

    def refresh(self) -> None:
        """
        Refresh page content using current investigation.
        """
        investigation = ApplicationState.get_current_investigation()
        if investigation is None:
            self._ioc_summary.reset()
            self._ioc_details.reset()
            return

        self._ioc_summary.load_investigation(investigation)
        self._ioc_details.reset()
