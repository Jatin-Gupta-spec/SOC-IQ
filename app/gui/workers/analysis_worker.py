"""
Background worker for SOC-IQ report analysis.

Runs the analysis engine on a background thread
without blocking the GUI.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.gui.controllers.analyze_controller import (
    AnalyzeController,
)


class AnalysisWorker(QObject):
    """
    Executes report analysis in a background thread.
    """

    started = Signal()

    finished = Signal(object)

    failed = Signal(str)

    def __init__(
        self,
        report_path: str,
    ) -> None:
        super().__init__()

        self._report_path = report_path

        self._controller = AnalyzeController()

    @Slot()
    def run(self) -> None:
        """
        Execute the report analysis.
        """

        self.started.emit()

        try:

            investigation = (
                self._controller.analyze(
                    self._report_path,
                )
            )

            self.finished.emit(
                investigation,
            )

        except Exception as error:

            self.failed.emit(
                str(error),
            )