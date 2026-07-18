"""
Background worker for SOC-IQ report analysis.

Runs the analysis engine on a background thread
without blocking the GUI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.analyzer import analyze_report


class AnalysisWorker(QObject):
    """
    Executes report analysis in a background thread.
    """

    started = Signal()

    finished = Signal(dict)

    failed = Signal(str)

    def __init__(
        self,
        report_path: str,
    ) -> None:
        super().__init__()

        self._report_path = report_path

    @Slot()
    def run(self) -> None:
        """
        Execute the report analysis.
        """

        self.started.emit()

        try:

            result: dict[str, Any] = analyze_report(
                Path(self._report_path)
            )

            self.finished.emit(result)

        except Exception as error:

            self.failed.emit(str(error))