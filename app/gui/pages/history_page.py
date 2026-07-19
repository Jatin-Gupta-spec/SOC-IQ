"""
Investigation history page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.gui.controllers.history_controller import HistoryController
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.models.investigation_table_model import (
    InvestigationTableModel,
)
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.section_header import SectionHeader


class HistoryPage(QWidget):
    """
    Displays previously analyzed investigations.
    """

    def __init__(self) -> None:
        super().__init__()

        self._controller = HistoryController()

        self._model = InvestigationTableModel()

        self._table = QTableView()

        self._search_box = QLineEdit()

        self._search_box.setPlaceholderText(
            "Search by report, severity or status..."
        )

        self._container = PageContainer(
            title="Investigation History",
            description=(
                "Browse investigations stored in the "
                "SOC-IQ database."
            ),
        )

        self._build_ui()

        self._connect_signals()

        self.refresh()

    def _build_ui(self) -> None:
        """
        Build the page layout.
        """

        layout = self._container.content_layout()

        layout.addWidget(
            SectionHeader(
                "Recent Investigations",
                (
                    "Latest completed investigations "
                    "stored in the database."
                ),
            )
        )

        layout.addWidget(
            self._search_box,
        )

        self._table.setModel(self._model)

        self._table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )

        self._table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )

        self._table.setAlternatingRowColors(True)

        self._table.setSortingEnabled(False)

        self._table.verticalHeader().setVisible(False)

        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        layout.addWidget(
            self._table
        )

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

    def _connect_signals(self) -> None:
        """
        Connect widget signals.
        """

        self._table.doubleClicked.connect(
            self._open_investigation
        )

        self._search_box.textChanged.connect(
            self._filter_investigations,
        )

    def _open_investigation(
        self,
        index: QModelIndex,
    ) -> None:
        """
        Handle double-click on an investigation.
        """

        investigation = self._model.investigation_at(
            index.row()
        )

        if investigation is None:
            return

        ApplicationState.current_investigation = (
            investigation
        )

        event_bus.investigation_selected.emit()

        print(
            "Selected investigation:",
            investigation.report_name,
        )

    def _filter_investigations(
        self,
        text: str,
    ) -> None:
        """
        Filter investigations by report,
        severity, or status.
        """

        self._model.filter(
            text,
        )

    def refresh(self) -> None:
        """
        Reload investigations from the controller.
        """

        investigations = (
            self._controller.get_recent_investigations()
        )

        self._model.set_investigations(
            investigations,
        )