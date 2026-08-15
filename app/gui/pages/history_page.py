"""
Investigation history page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.layout.component_section import ComponentSection
from app.gui.controllers.history_controller import HistoryController
from app.gui.events.application_state import ApplicationState
from app.gui.events.event_bus import event_bus
from app.gui.models.investigation_table_model import (
    InvestigationTableModel,
)
from app.gui.utils.csv_exporter import (
    export_investigations_to_csv,
)
from app.gui.widgets.investigation_statistics_widget import (
    InvestigationStatisticsWidget,
)
from app.gui.widgets.page_container import PageContainer


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

        self._search_box.setClearButtonEnabled(
            True,
        )

        self._export_button = QPushButton(
            "Export CSV",
        )

        self._statistics_widget = (
            InvestigationStatisticsWidget()
        )

        # Shown in place of the table when there are zero rows to
        # display -- either because the database has no investigations
        # yet, or because the current search text matches nothing.
        # Previously this state rendered as a bare, blank table grid,
        # which is indistinguishable from "the page is still loading"
        # or "something broke" to an analyst.
        self._empty_state_label = QLabel()
        self._empty_state_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.hide()

        self._container = PageContainer(
            title="Investigation History",
            description=(
                "Browse investigations stored in the "
                "SOC-IQ database."
            ),
        )

        # Previously this page's "Recent Investigations" heading was
        # a bare SectionHeader added directly to the page layout,
        # with the toolbar/stats/table added as page-level siblings
        # underneath it. Every other page (IOC Viewer, Risk
        # Dashboard, Threat Intel, Settings) instead wraps its
        # content inside a ComponentSection, which owns the header
        # AND the spacing to its content via add_widget()/
        # add_layout(). ComponentSection already builds its header
        # from the same title/description constructor shape, so this
        # is a drop-in swap that brings History in line with the
        # rest of the app's section composition.
        self._section = ComponentSection(
            title="Recent Investigations",
            description=(
                "Latest completed investigations "
                "stored in the database."
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

        toolbar_layout = QHBoxLayout()

        toolbar_layout.addWidget(
            self._search_box,
        )

        toolbar_layout.addWidget(
            self._export_button,
        )

        self._section.add_layout(
            toolbar_layout,
        )

        self._section.add_widget(
            self._statistics_widget,
        )

        self._table.setModel(
            self._model,
        )

        self._table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows,
        )

        self._table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection,
        )

        self._table.setAlternatingRowColors(
            True,
        )

        self._table.setSortingEnabled(
            True,
        )

        self._table.verticalHeader().setVisible(
            False,
        )

        self._table.horizontalHeader().setStretchLastSection(
            True,
        )

        self._table.horizontalHeader().setSortIndicatorShown(
            True,
        )

        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self._section.add_widget(
            self._table,
        )

        self._section.add_widget(
            self._empty_state_label,
        )

        layout.addWidget(
            self._section,
        )

        root_layout = QVBoxLayout()

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.addWidget(
            self._container,
        )

        self.setLayout(
            root_layout,
        )

    def _connect_signals(self) -> None:
        """
        Connect widget signals.
        """

        self._table.doubleClicked.connect(
            self._open_investigation,
        )

        self._search_box.textChanged.connect(
            self._filter_investigations,
        )

        self._export_button.clicked.connect(
            self._export_csv,
        )

        event_bus.investigation_created.connect(
            self.refresh,
        )

    def _open_investigation(
        self,
        index: QModelIndex,
    ) -> None:
        """
        Handle double-click on an investigation.
        """

        investigation = self._model.investigation_at(
            index.row(),
        )

        if investigation is None:
            return

        ApplicationState.select_investigation(
            investigation,
        )

    def _filter_investigations(
        self,
        text: str,
    ) -> None:
        """
        Filter investigations by report name,
        severity, or status.
        """

        self._model.filter(
            text,
        )

        self._update_empty_state()

    def _update_empty_state(self) -> None:
        """
        Show a message in place of the table when it has zero
        rows, and distinguish "no investigations exist yet" from
        "no investigations match the current search" so the
        analyst knows whether to clear the search box or run an
        investigation.
        """

        has_rows = self._model.rowCount() > 0

        self._table.setVisible(has_rows)
        self._empty_state_label.setVisible(not has_rows)

        if has_rows:
            return

        if self._search_box.text().strip():
            self._empty_state_label.setText(
                "No investigations match your search."
            )
        else:
            self._empty_state_label.setText(
                "No investigations yet. Completed investigations "
                "will appear here."
            )

    def _export_csv(
        self,
    ) -> None:
        """
        Export investigations to a CSV file.
        """

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Investigations",
            "investigations.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        # Export exactly what is currently shown in the table (respecting
        # any active search filter), rather than re-querying the
        # controller for a "recent investigations" set that may differ
        # from -- or be more/less limited than -- what the user is
        # looking at.
        row_count = self._model.rowCount()
        investigations = [
            investigation
            for row in range(row_count)
            if (investigation := self._model.investigation_at(row)) is not None
        ]

        if not investigations:
            QMessageBox.information(
                self,
                "Nothing to Export",
                "There are no investigations to export.",
            )
            return

        try:

            export_investigations_to_csv(
                investigations,
                file_path,
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Export Failed",
                str(error),
            )

            return

        QMessageBox.information(
            self,
            "Export Complete",
            (
                "Investigation history was exported "
                "successfully."
            ),
        )

    def refresh(self) -> None:
        """
        Reload investigations from the controller.
        """

        try:
            investigations = (
                self._controller.get_recent_investigations()
            )
        except Exception as error:
            # Leave the currently displayed data in place rather than
            # clearing it to an empty list, since an empty list would be
            # indistinguishable from "no investigations exist" -- a
            # database/controller failure must never be shown as an
            # empty state.
            QMessageBox.critical(
                self,
                "Unable to Load Investigations",
                (
                    "Investigation history could not be loaded from the "
                    f"database:\n\n{error}"
                ),
            )
            return

        self._model.set_investigations(
            investigations,
        )

        self._statistics_widget.load_investigations(
            investigations,
        )

        self._model.filter(
            self._search_box.text(),
        )

        self._update_empty_state()