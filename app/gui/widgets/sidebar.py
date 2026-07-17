"""
Sidebar widget for the SOC-IQ desktop application.

This module contains the application's primary navigation panel.
The widget is responsible only for presenting navigation buttons
and notifying other components when a button is selected.
"""

from __future__ import annotations

from enum import IntEnum

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class NavigationPage(IntEnum):
    """Application page indexes."""

    DASHBOARD = 0
    ANALYZE = 1
    IOC_VIEWER = 2
    THREAT_INTELLIGENCE = 3
    RISK_DASHBOARD = 4
    HISTORY = 5
    SETTINGS = 6


class SidebarWidget(QWidget):
    """
    Sidebar navigation widget.
    """

    page_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the sidebar user interface.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(10, 10, 10, 10)

        layout.setSpacing(8)

        buttons = (
            ("Dashboard", NavigationPage.DASHBOARD),
            ("Analyze Report", NavigationPage.ANALYZE),
            ("IOC Viewer", NavigationPage.IOC_VIEWER),
            ("Threat Intelligence", NavigationPage.THREAT_INTELLIGENCE),
            ("Risk Dashboard", NavigationPage.RISK_DASHBOARD),
            ("Investigation History", NavigationPage.HISTORY),
            ("Settings", NavigationPage.SETTINGS),
        )

        for text, page in buttons:
            button = QPushButton(text)

            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            button.clicked.connect(
                lambda checked=False, page_index=int(page): (
                    self.page_selected.emit(page_index)
                )
            )

            layout.addWidget(button)

        layout.addStretch()

        self.setLayout(layout)