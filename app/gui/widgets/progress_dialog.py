"""
Professional progress dialog for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
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
            420,
            240,
        )

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False,
        )