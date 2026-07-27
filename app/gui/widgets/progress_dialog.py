"""
Professional progress dialog for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    QTimer,
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

    @property
    def elapsed_seconds(
        self,
    ) -> int:
        """
        Return elapsed seconds.
        """

        return self._elapsed_seconds