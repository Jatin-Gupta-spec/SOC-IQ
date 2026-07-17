"""
Main application window for SOC-IQ.

This module defines the primary window for the desktop application.
Additional GUI components (menu bar, toolbar, sidebar, pages, etc.)
will be added incrementally during Phase 4.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """
    Primary application window.
    """

    def __init__(self) -> None:
        super().__init__()

        self._configure_window()

    def _configure_window(self) -> None:
        """
        Configure the initial window properties.
        """

        self.setWindowTitle("SOC-IQ")
        self.resize(1400, 900)

        self.setMinimumSize(1100, 700)

        self.setCentralWidget(None)

        self.statusBar().showMessage("SOC-IQ Ready")

        self.setUnifiedTitleAndToolBarOnMac(False)