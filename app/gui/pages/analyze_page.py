"""
Analyze Report page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from app.database.models import Investigation
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.exceptions import DuplicateInvestigationError
from app.gui.controllers.analyze_controller import AnalyzeController
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.section_header import SectionHeader
from app.gui.workers.analysis_worker import AnalysisWorker


class AnalyzePage(QWidget):
    """
    Page used to analyze malware reports.
    """

    analysis_completed = Signal(object)

    def __init__(self) -> None:
        super().__init__()

        self._controller = AnalyzeController()

        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None

        self._container = PageContainer(
            title="Analyze Report",
            description=(
                "Select a malware report and begin a complete "
                "SOC-IQ investigation."
            ),
        )

        self._report_path = QLineEdit()
        self._browse_button = QPushButton("Browse...")
        self._analyze_button = QPushButton("Analyze Report")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """
        Build the page layout.
        """

        layout = self._container.content_layout()

        layout.addWidget(
            SectionHeader(
                "Report Selection",
                "Choose a malware report to analyze.",
            )
        )

        self._report_path.setReadOnly(True)

        self._report_path.setPlaceholderText(
            "No report selected..."
        )

        self._analyze_button.setEnabled(False)

        button_layout = QHBoxLayout()

        button_layout.addWidget(
            self._browse_button,
        )

        button_layout.addWidget(
            self._analyze_button,
        )

        layout.addWidget(
            QLabel(
                "Selected Report",
            )
        )

        layout.addWidget(
            self._report_path,
        )

        layout.addLayout(
            button_layout,
        )

        layout.addStretch()

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

        self._browse_button.clicked.connect(
            self._browse_report,
        )

        self._analyze_button.clicked.connect(
            self._start_analysis,
        )

    def _browse_report(self) -> None:
        """
        Open a file dialog for selecting a report.
        """

        report_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Malware Report",
            "",
            "Text Files (*.txt);;All Files (*)",
        )

        if not report_path:
            return

        self._report_path.setText(
            report_path,
        )

        self._analyze_button.setEnabled(
            self._controller.validate_report(
                report_path,
            )
        )

    def _start_analysis(self) -> None:
        """
        Start report analysis in a background thread.
        """

        report_path = self._report_path.text()

        self._thread = QThread(self)

        self._worker = AnalysisWorker(
            report_path,
        )

        self._worker.moveToThread(
            self._thread,
        )

        self._thread.started.connect(
            self._worker.run,
        )

        self._worker.started.connect(
            self._on_analysis_started,
        )

        self._worker.finished.connect(
            self._on_analysis_finished,
        )

        self._worker.failed.connect(
            self._on_analysis_failed,
        )

        self._worker.finished.connect(
            self._thread.quit,
        )

        self._worker.failed.connect(
            self._thread.quit,
        )

        self._thread.finished.connect(
            self._worker.deleteLater,
        )

        self._thread.finished.connect(
            self._thread.deleteLater,
        )

        self._thread.start()

    def _on_analysis_started(self) -> None:
        """
        Handle analysis start.
        """

        self._browse_button.setEnabled(False)

        self._analyze_button.setEnabled(False)

    def _on_analysis_finished(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Handle successful analysis.
        """

        self._browse_button.setEnabled(True)

        self._analyze_button.setEnabled(True)

        QMessageBox.information(
            self,
            "Analysis Complete",
            (
                f"Report '{investigation.report_name}' "
                "analyzed successfully."
            ),
        )

        self.analysis_completed.emit(
            investigation,
        )

    def _on_analysis_failed(
        self,
        message: str,
    ) -> None:
        """
        Handle analysis failure.
        """

        self._browse_button.setEnabled(True)

        self._analyze_button.setEnabled(True)

        if "DuplicateInvestigationError" in message:

            QMessageBox.warning(
                self,
                "Investigation Already Exists",
                (
                    "This malware report has already been "
                    "analyzed.\n\n"
                    "SOC-IQ prevents duplicate investigations "
                    "to maintain investigation integrity."
                ),
            )

            return

        QMessageBox.critical(
            self,
            "Analysis Failed",
            message,
        )