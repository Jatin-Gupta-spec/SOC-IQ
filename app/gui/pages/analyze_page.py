"""
Analyze Report page for the SOC-IQ desktop application.

Provides interactive malware report ingestion with Drag-and-Drop support,
background QThread execution, real-time progress modal, and toast feedback.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.file_dropzone import FileDropzoneWidget
from app.gui.components.feedback.toast_notification import (
    ToastNotification,
    ToastType,
)
from app.gui.components.layout.component_section import ComponentSection
from app.gui.controllers.analyze_controller import AnalyzeController
from app.gui.design.tokens import Spacing
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.progress_dialog import ProgressDialog
from app.gui.widgets.section_header import SectionHeader
from app.gui.workers.analysis_worker import AnalysisWorker


class AnalyzePage(QWidget):
    """
    Page used to analyze malware reports.
    """

    analysis_completed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._controller = AnalyzeController()

        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None

        self._progress_dialog = ProgressDialog(self)

        self._container = PageContainer(
            title="Ingest & Analyze Report",
            description=(
                "Select or drag-and-drop a malware report to begin a complete "
                "SOC-IQ forensic investigation."
            ),
        )

        self._dropzone = FileDropzoneWidget()
        self._report_path = QLineEdit()
        self._browse_button = AnimatedButton("Browse Files...")
        self._analyze_button = AnimatedButton("Execute Analysis")

        self._toast_box = QVBoxLayout()

        self._chk_iocs = QCheckBox("Extract Indicators of Compromise (IOCs)")
        self._chk_vt = QCheckBox("Enable VirusTotal Threat Intelligence Enrichment")
        self._chk_risk = QCheckBox("Perform Automated Risk Scoring")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """
        Build the page layout.
        """
        layout = self._container.content_layout()

        # Ingestion Section
        ingest_section = ComponentSection(
            title="Report Ingestion Dropzone",
            description="Drag and drop your malware analysis text/log file below.",
        )

        ingest_box = QVBoxLayout()
        ingest_box.setSpacing(Spacing.MD)

        ingest_box.addWidget(self._dropzone)

        # Text input & buttons
        self._report_path.setReadOnly(True)
        self._report_path.setPlaceholderText("No report file selected...")
        self._analyze_button.setEnabled(False)

        path_row = QHBoxLayout()
        path_row.setSpacing(Spacing.MD)
        path_row.addWidget(self._report_path, 3)
        path_row.addWidget(self._browse_button, 1)
        path_row.addWidget(self._analyze_button, 1)

        ingest_box.addLayout(path_row)
        ingest_section.add_layout(ingest_box)

        layout.addWidget(ingest_section)

        # Options Section
        options_card = ModernCard()
        opt_layout = QVBoxLayout()
        opt_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        opt_layout.setSpacing(Spacing.SM)

        opt_title = QLabel("Analysis Execution Pipeline")
        palette = options_card.theme.palette
        fonts = options_card.theme.fonts

        opt_title.setFont(fonts.title())
        opt_title.setStyleSheet(f"color: {palette.text_primary}; font-weight: 600;")

        self._chk_iocs.setChecked(True)
        self._chk_vt.setChecked(True)
        self._chk_risk.setChecked(True)

        for chk in (self._chk_iocs, self._chk_vt, self._chk_risk):
            chk.setFont(fonts.body())
            chk.setStyleSheet(f"color: {palette.text_secondary};")

        opt_layout.addWidget(opt_title)
        opt_layout.addWidget(self._chk_iocs)
        opt_layout.addWidget(self._chk_vt)
        opt_layout.addWidget(self._chk_risk)

        options_card.add_layout(opt_layout)
        layout.addWidget(options_card)

        # Toast notification holder
        layout.addLayout(self._toast_box)

        layout.addStretch()

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

        self.setLayout(root_layout)

    def _connect_signals(self) -> None:
        """
        Connect widget signals.
        """
        self._browse_button.clicked.connect(self._browse_report)
        self._dropzone.clicked.connect(self._browse_report)
        self._dropzone.file_dropped.connect(self._on_file_selected)

        self._analyze_button.clicked.connect(self._start_analysis)

    def _on_file_selected(self, report_path: str) -> None:
        """
        Handle report file selection.
        """
        if not report_path:
            return

        self._report_path.setText(report_path)
        self._dropzone.set_file_path(report_path)

        is_valid = self._controller.validate_report(report_path)
        self._analyze_button.setEnabled(is_valid)

        if is_valid:
            self._show_toast("Report file validated successfully.", ToastType.INFO)
        else:
            self._show_toast("Invalid or empty report file.", ToastType.ERROR)

    def _browse_report(self) -> None:
        """
        Open a file dialog for selecting a report.
        """
        report_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Malware Report",
            "",
            "Text Files (*.txt);;Log Files (*.log);;All Files (*)",
        )

        if report_path:
            self._on_file_selected(report_path)

    def _show_toast(self, message: str, toast_type: ToastType) -> None:
        """
        Display ephemeral toast notification.
        """
        # Clear existing toasts
        while self._toast_box.count():
            child = self._toast_box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        toast = ToastNotification(message, toast_type)
        self._toast_box.addWidget(toast)

    def _start_analysis(self) -> None:
        """
        Start report analysis in a background thread.
        """
        report_path = self._report_path.text()

        self._thread = QThread(self)
        self._worker = AnalysisWorker(report_path)

        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(self._on_analysis_started)
        self._worker.progress_changed.connect(self._on_progress_changed)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.failed.connect(self._on_analysis_failed)

        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)

        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_analysis_started(self) -> None:
        """
        Handle analysis start.
        """
        self._browse_button.setEnabled(False)
        self._analyze_button.setEnabled(False)

        self._progress_dialog.reset()
        self._progress_dialog.show()

    def _on_progress_changed(self, value: int, message: str) -> None:
        """
        Update the progress dialog.
        """
        self._progress_dialog.set_progress(value)
        self._progress_dialog.set_status(message)

        if value >= 100:
            self._progress_dialog.finish_activity(message)
        else:
            self._progress_dialog.add_activity(message)

    def _on_analysis_finished(self, result: dict[str, Any]) -> None:
        """
        Handle successful analysis.
        """
        self._browse_button.setEnabled(True)
        self._analyze_button.setEnabled(True)

        self._progress_dialog.hide()

        investigation = result["investigation"]
        existing = result["existing"]

        if existing:
            self._show_toast(
                f"Existing investigation loaded: {investigation.report_name}",
                ToastType.INFO,
            )
            QMessageBox.information(
                self,
                "Investigation Already Exists",
                (
                    f"Report '{investigation.report_name}' has already been analyzed.\n\n"
                    "Opening existing investigation workspace."
                ),
            )
        else:
            self._show_toast(
                f"Analysis completed successfully: {investigation.report_name}",
                ToastType.SUCCESS,
            )

        self.analysis_completed.emit(investigation)

    def _on_analysis_failed(self, message: str) -> None:
        """
        Handle analysis failure.
        """
        self._browse_button.setEnabled(True)
        self._analyze_button.setEnabled(True)

        self._progress_dialog.hide()

        self._show_toast(f"Analysis failed: {message}", ToastType.ERROR)
        QMessageBox.critical(
            self,
            "Analysis Failed",
            message,
        )