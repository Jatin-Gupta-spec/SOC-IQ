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

    Each instance is bound to a single ``report_path`` and is meant
    to be run exactly once. Nothing in the surrounding thread/signal
    wiring (owned outside this file, e.g. by the page that creates
    the ``QThread``) is visible here, so this class defends itself
    against being entered twice for the same instance — e.g. because
    of a duplicate ``started``/``run`` signal connection — since that
    would otherwise emit ``started``/``finished``/``failed`` twice
    and could trigger duplicate downstream side effects (persistence,
    investigation creation) via the controller.
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

        self._has_run = False

    @Slot()
    def run(self) -> None:
        """
        Execute the report analysis.
        """

        if self._has_run:
            logger.warning(
                "AnalysisWorker.run() called more than once for "
                "'%s'; ignoring the repeat invocation to avoid "
                "duplicate signal emissions and duplicate side "
                "effects.",
                self._report_path,
            )
            return

        self._has_run = True

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