"""
Reusable Investigation Statistics widget for the
SOC-IQ desktop application.

Displays summary statistics about investigations
stored in the SOC-IQ database.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QGridLayout,
    QWidget,
)


class InvestigationStatisticsWidget(QWidget):
    """
    Displays investigation statistics.
    """

    def __init__(self) -> None:
        super().__init__()

        self._total_label = QLabel("0")
        self._critical_label = QLabel("0")
        self._high_label = QLabel("0")
        self._medium_label = QLabel("0")
        self._low_label = QLabel("0")

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        layout = QGridLayout()

        layout.addWidget(
            QLabel("Total Investigations"),
            0,
            0,
        )

        layout.addWidget(
            self._total_label,
            0,
            1,
        )

        layout.addWidget(
            QLabel("Critical"),
            1,
            0,
        )

        layout.addWidget(
            self._critical_label,
            1,
            1,
        )

        layout.addWidget(
            QLabel("High"),
            2,
            0,
        )

        layout.addWidget(
            self._high_label,
            2,
            1,
        )

        layout.addWidget(
            QLabel("Medium"),
            3,
            0,
        )

        layout.addWidget(
            self._medium_label,
            3,
            1,
        )

        layout.addWidget(
            QLabel("Low"),
            4,
            0,
        )

        layout.addWidget(
            self._low_label,
            4,
            1,
        )

        self.setLayout(
            layout,
        )

    def reset(self) -> None:
        """
        Reset all statistics.
        """

        self._total_label.setText("0")
        self._critical_label.setText("0")
        self._high_label.setText("0")
        self._medium_label.setText("0")
        self._low_label.setText("0")