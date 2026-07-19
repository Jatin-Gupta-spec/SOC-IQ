"""
Investigation history page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
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
from app.gui.utils.csv_exporter import (
    export_investigations_to_csv,
)
from app.gui.widgets.investigation_statistics_widget import (
    InvestigationStatisticsWidget,
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

        self._search_box.setClearButtonEnabled(
            True,
        )

        self._export_button = QPushButton(
            "Export CSV",
        )

        self._statistics_widget = (
            InvestigationStatisticsWidget()
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

        toolbar_layout = QHBoxLayout()

        toolbar_layout.addWidget(
            self._search_box,
        )

        toolbar_layout.addWidget(
            self._export_button,
        )

        layout.addLayout(
            toolbar_layout,
        )

        layout.addWidget(
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

        layout.addWidget(
            self._table,
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

        investigations = (
            self._controller.get_recent_investigations()
        )

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

        investigations = (
            self._controller.get_recent_investigations()
        )

        self._model.set_investigations(
            investigations,
        )

        self._statistics_widget.load_investigations(
            investigations,
        )

        self._model.filter(
            self._search_box.text(),
        )