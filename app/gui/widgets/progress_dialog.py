"""
Professional progress dialog for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from PySide6.QtGui import (
    QFont,
)

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
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
            420,
            240,
        )

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False,
        )

        # ------------------------------------------
        # Widgets
        # ------------------------------------------

        self._title_label = QLabel(
            "Analysing Investigation",
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
            "Preparing analysis...",
        )

        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self._progress_bar = QProgressBar()

        self._progress_bar.setMinimum(
            0,
        )

        self._progress_bar.setMaximum(
            100,
        )

        self._progress_bar.setValue(
            0,
        )

        self._progress_bar.setTextVisible(
            True,
        )

        self._elapsed_label = QLabel(
            "Elapsed: 00:00",
        )

        self._cancel_button = QPushButton(
            "Cancel",
        )

        self._cancel_button.setMinimumHeight(
            36,
        )

        # ------------------------------------------
        # Layout
        # ------------------------------------------

        layout = QVBoxLayout()

        layout.setContentsMargins(
            30,
            30,
            30,
            30,
        )

        layout.setSpacing(
            18,
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

        def set_progress(
            self,
            value: int,
        ) -> None:
            """
            Update the progress bar value.
            """

            self._progress_bar.setValue(
                value,
            )