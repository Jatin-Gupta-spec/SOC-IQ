"""
Main application window for SOC-IQ.

This module defines the primary window for the desktop application.
The window structure created here serves as the foundation for all
future GUI pages and widgets.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.sidebar import SidebarWidget


class MainWindow(QMainWindow):
    """
    Primary application window.
    """

    def __init__(self) -> None:
        super().__init__()

        self.page_stack = QStackedWidget()
        self.sidebar = SidebarWidget()

        self._configure_window()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_central_widget()
        self._create_status_bar()
        self._create_pages()
        self._connect_signals()

    def _configure_window(self) -> None:
        """
        Configure the main application window.
        """

        self.setWindowTitle("SOC-IQ")

        self.resize(1400, 900)

        self.setMinimumSize(1100, 700)

        self.setUnifiedTitleAndToolBarOnMac(False)

    def _create_menu_bar(self) -> None:
        """
        Create the application menu bar.
        """

        menu_bar = self.menuBar()

        menu_bar.addMenu("File")
        menu_bar.addMenu("View")
        menu_bar.addMenu("Tools")
        menu_bar.addMenu("Help")

    def _create_tool_bar(self) -> None:
        """
        Create the main application toolbar.
        """

        toolbar = QToolBar("Main Toolbar")

        toolbar.setMovable(False)

        self.addToolBar(Qt.TopToolBarArea, toolbar)

        analyze_action = QAction("Analyze", self)

        toolbar.addAction(analyze_action)

    def _create_central_widget(self) -> None:
        """
        Create the application's central widget.
        """

        central_widget = QWidget()

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        self.sidebar.setFixedWidth(240)

        main_layout.addWidget(self.sidebar)

        page_layout = QVBoxLayout()

        page_layout.setContentsMargins(0, 0, 0, 0)

        page_layout.addWidget(self.page_stack)

        main_layout.addLayout(page_layout)

        central_widget.setLayout(main_layout)

        self.setCentralWidget(central_widget)

    def _create_pages(self) -> None:
        """
        Create placeholder application pages.
        """

        page_names = (
            "Dashboard",
            "Analyze Report",
            "IOC Viewer",
            "Threat Intelligence",
            "Risk Dashboard",
            "Investigation History",
            "Settings",
        )

        for page_name in page_names:
            page = QWidget()

            layout = QVBoxLayout(page)

            label = QLabel(page_name)

            label.setAlignment(Qt.AlignCenter)

            layout.addWidget(label)

            self.page_stack.addWidget(page)

    def _connect_signals(self) -> None:
        """
        Connect GUI signals.
        """

        self.sidebar.page_selected.connect(
            self.page_stack.setCurrentIndex
        )

    def _create_status_bar(self) -> None:
        """
        Create the application status bar.
        """

        self.statusBar().showMessage("SOC-IQ Ready")