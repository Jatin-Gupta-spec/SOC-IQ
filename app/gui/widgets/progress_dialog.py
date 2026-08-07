"""
Professional progress dialog for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QFont,
)

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressDialog(QDialog):
    """
    Professional progress dialog used by SOC-IQ.
    """

    # Exposes cancellation as a proper signal instead of
    # requiring callers to reach into the private
    # `_cancel_button` attribute and connect to its
    # `clicked` signal directly, which broke encapsulation.
    canceled = Signal()

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "SOC-IQ",
        )

        self.setModal(
            True,
        )

        self.setFixedSize(
            430,
            360,
        )

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False,
        )

        # ------------------------------------------
        # Timer
        # ------------------------------------------

        self._elapsed_seconds = 0

        self._timer = QTimer(self)

        self._timer.timeout.connect(
            self._update_elapsed_time,
        )

        self._timer.start(
            1000,
        )

        # ------------------------------------------
        # Widgets
        # ------------------------------------------

        self._title_label = QLabel(
            "SOC-IQ Investigation"
        )

        title_font = QFont()

        title_font.setPointSize(
            15,
        )

        title_font.setBold(
            True,
        )

        self._title_label.setFont(
            title_font,
        )

        self._title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self._status_label = QLabel(
            "Preparing analysis..."
        )

        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self._progress_bar = QProgressBar()

        self._progress_bar.setRange(
            0,
            100,
        )

        self._progress_bar.setValue(
            0,
        )

        self._progress_bar.setTextVisible(
            True,
        )

        self._activity_log = QListWidget()

        self._activity_log.setFocusPolicy(
            Qt.FocusPolicy.NoFocus,
        )

        self._activity_log.setMaximumHeight(
            120,
        )

        self._elapsed_label = QLabel(
            "Elapsed: 00:00"
        )

        self._cancel_button = QPushButton(
            "Cancel"
        )

        self._cancel_button.setMinimumHeight(
            36,
        )

        self._cancel_button.clicked.connect(
            self.canceled.emit,
        )

        # ------------------------------------------
        # Layout
        # ------------------------------------------

        layout = QVBoxLayout()

        layout.setContentsMargins(
            25,
            25,
            25,
            25,
        )

        layout.setSpacing(
            16,
        )

        layout.addWidget(
            self._title_label,
        )

        layout.addWidget(
            self._status_label,
        )

        layout.addWidget(
            self._progress_bar,
        )

        layout.addWidget(
            self._activity_log,
        )

        elapsed_layout = QHBoxLayout()

        elapsed_layout.addWidget(
            self._elapsed_label,
        )

        elapsed_layout.addStretch()

        layout.addLayout(
            elapsed_layout,
        )

        layout.addStretch()

        layout.addWidget(
            self._cancel_button,
        )

        self.setLayout(
            layout,
        )

    # ==================================================
    # Lifecycle
    # ==================================================

    def closeEvent(self, event) -> None:
        """
        Stop the elapsed-time timer when the dialog closes.

        Previously the QTimer kept firing every second even
        after the dialog was closed (via Cancel, the window
        X button, or a caller calling `.close()`/`.reject()`
        directly). On PySide6, a running QTimer that still
        targets a since-deleted/hidden dialog is a real
        crash risk ("Internal C++ object already deleted")
        and, at minimum, a background timer leak for the
        lifetime of the parent widget.
        """

        self._timer.stop()
        super().closeEvent(event)

    # ==================================================
    # Timer
    # ==================================================

    def _update_elapsed_time(
        self,
    ) -> None:
        """
        Update elapsed time every second.
        """

        self._elapsed_seconds += 1

        minutes = (
            self._elapsed_seconds // 60
        )

        seconds = (
            self._elapsed_seconds % 60
        )

        self._elapsed_label.setText(
            f"Elapsed: {minutes:02}:{seconds:02}"
        )

    # ==================================================
    # Public API
    # ==================================================

    def set_progress(
        self,
        value: int,
    ) -> None:
        """
        Update the progress bar.
        """

        self._progress_bar.setValue(
            value,
        )

    def set_status(
        self,
        message: str,
    ) -> None:
        """
        Update the current status.
        """

        self._status_label.setText(
            message,
        )

    def add_activity(
        self,
        message: str,
    ) -> None:
        """
        Add a new activity.
        """

        count = self._activity_log.count()

        if count > 0:

            previous = self._activity_log.item(
                count - 1,
            )

            if previous.text().startswith(
                "⏳",
            ):

                previous.setText(
                    previous.text().replace(
                        "⏳",
                        "✓",
                        1,
                    )
                )

        self._activity_log.addItem(
            f"⏳ {message}",
        )

        self._activity_log.scrollToBottom()

    def finish_activity(
        self,
        message: str,
    ) -> None:
        """
        Mark the investigation as complete.
        """

        count = self._activity_log.count()

        if count > 0:

            last = self._activity_log.item(
                count - 1,
            )

            last.setText(
                f"✔ {message}"
            )

    def reset(
        self,
    ) -> None:
        """
        Reset the dialog for a new analysis.
        """

        self._progress_bar.setValue(
            0,
        )

        self._status_label.setText(
            "Preparing analysis...",
        )

        self._activity_log.clear()

        self._elapsed_seconds = 0

        self._elapsed_label.setText(
            "Elapsed: 00:00",
        )

        # If the dialog was previously closed (which now
        # stops the timer), reusing it for a new analysis
        # must restart the clock — otherwise elapsed time
        # would silently freeze forever on a reused dialog.
        if not self._timer.isActive():
            self._timer.start(1000)

    @property
    def elapsed_seconds(
        self,
    ) -> int:
        """
        Return elapsed seconds.
        """

        return self._elapsed_seconds