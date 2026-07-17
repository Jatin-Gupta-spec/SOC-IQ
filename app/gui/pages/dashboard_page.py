"""
Dashboard page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    """
    Dashboard page displayed when the application starts.
    """

    def __init__(self) -> None:
        super().__init__()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the dashboard user interface.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("SOC-IQ Dashboard")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: bold;
            """
        )

        subtitle = QLabel(
            "Security Operations Center - Intelligence & IOC Analysis"
        )

        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle.setStyleSheet(
            """
            font-size: 14px;
            color: gray;
            """
        )

        layout.addStretch()

        layout.addWidget(title)

        layout.addWidget(subtitle)

        layout.addStretch()

        self.setLayout(layout)