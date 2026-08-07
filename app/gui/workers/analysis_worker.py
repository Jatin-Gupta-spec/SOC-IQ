"""
Background worker for SOC-IQ report analysis.

Runs the analysis engine on a background thread
without blocking the GUI.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.gui.controllers.analyze_controller import (
    AnalyzeController,
)

logger = logging.getLogger(__name__)


class AnalysisWorker(QObject):
    """
    Executes report analysis in a background thread.
    """

    started = Signal()

    progress_changed = Signal(
        int,
        str,
    )

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

            result: dict[str, Any] = (
                self._controller.analyze(
                    self._report_path,
                    progress_callback=self.progress_changed.emit,
                )
            )

            self.finished.emit(
                result,
            )

        except Exception as error:

            # Without this, failures were only ever
            # surfaced to the user as a bare `str(error)`
            # message via the `failed` signal, with no
            # record of the traceback anywhere. That makes
            # production incidents (e.g. a malformed report,
            # a threat-intel client bug) effectively
            # undebuggable after the fact.
            logger.exception(
                "Report analysis failed for '%s'.",
                self._report_path,
            )

            self.failed.emit(
                str(error),
            )