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
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.gui.events.application_state import (
    ApplicationState,
)
from app.gui.events.event_bus import (
    event_bus,
)
from app.gui.pages.analyze_page import (
    AnalyzePage,
)
from app.gui.pages.dashboard_page import (
    DashboardPage,
)
from app.gui.pages.history_page import (
    HistoryPage,
)
from app.gui.pages.investigation_workspace import (
    InvestigationWorkspacePage,
)
from app.gui.widgets.sidebar import (
    SidebarWidget,
)


class MainWindow(QMainWindow):
    """
    Primary application window.
    """

    WORKSPACE_PAGE_INDEX = 7

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

        self.setWindowTitle(
            "SOC-IQ"
        )

        self.resize(
            1400,
            900,
        )

        self.setMinimumSize(
            1100,
            700,
        )

        self.setUnifiedTitleAndToolBarOnMac(
            False,
        )

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

        toolbar = QToolBar(
            "Main Toolbar",
        )

        toolbar.setMovable(
            False,
        )

        self.addToolBar(
            Qt.ToolBarArea.TopToolBarArea,
            toolbar,
        )

        analyze_action = QAction(
            "Analyze",
            self,
        )

        toolbar.addAction(
            analyze_action,
        )

    def _create_central_widget(self) -> None:
        """
        Create the application's central widget.
        """

        central_widget = QWidget()

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        main_layout.setSpacing(
            0,
        )

        self.sidebar.setFixedWidth(
            240,
        )

        main_layout.addWidget(
            self.sidebar,
        )

        page_layout = QVBoxLayout()

        page_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        page_layout.addWidget(
            self.page_stack,
        )

        main_layout.addLayout(
            page_layout,
        )

        central_widget.setLayout(
            main_layout,
        )

        self.setCentralWidget(
            central_widget,
        )

    def _create_pages(self) -> None:
        """
        Create application pages.
        """

        self.dashboard_page = DashboardPage()

        self.analyze_page = AnalyzePage()

        self.ioc_page = QWidget()

        self.threat_page = QWidget()

        self.risk_page = QWidget()

        self.history_page = HistoryPage()

        self.settings_page = QWidget()

        self.workspace_page = (
            InvestigationWorkspacePage()
        )

        self.page_stack.addWidget(
            self.dashboard_page,
        )

        self.page_stack.addWidget(
            self.analyze_page,
        )

        self.page_stack.addWidget(
            self.ioc_page,
        )

        self.page_stack.addWidget(
            self.threat_page,
        )

        self.page_stack.addWidget(
            self.risk_page,
        )

        self.page_stack.addWidget(
            self.history_page,
        )

        self.page_stack.addWidget(
            self.settings_page,
        )

        self.page_stack.addWidget(
            self.workspace_page,
        )

    def _connect_signals(self) -> None:
        """
        Connect GUI signals.
        """

        self.sidebar.page_selected.connect(
            self.page_stack.setCurrentIndex,
        )

        event_bus.investigation_selected.connect(
            self._open_workspace,
        )

        self.analyze_page.analysis_completed.connect(
            self._analysis_completed,
        )
        

    def _open_workspace(self) -> None:
        """
        Open the Investigation Workspace.
        """

        investigation = (
            ApplicationState.get_current_investigation()
        )

        if investigation is None:
            print("\n===== OPEN WORKSPACE =====")
            print("Current investigation is None")
            print("==========================\n")
            return

        print("\n===== OPEN WORKSPACE =====")
        print(
            "ID:",
            investigation.investigation_id,
        )
        print(
            "Report:",
            investigation.report_name,
        )
        print(
            "Severity:",
            investigation.severity,
        )
        print(
            "Risk:",
            investigation.risk_score,
        )
        print(
            "Status:",
            investigation.status,
        )
        print("==========================\n")

        self.workspace_page.load_investigation(
            investigation,
        )

        self.page_stack.setCurrentIndex(
            self.WORKSPACE_PAGE_INDEX,
        )

        self.statusBar().showMessage(
            (
                f"Viewing investigation: "
                f"{investigation.report_name}"
            )
        )

    def _analysis_completed(
        self,
        investigation,
    ) -> None:
        """
        Handle a completed analysis.
        """

        ApplicationState.select_investigation(
            investigation,
        )

        self.history_page.refresh()

        if hasattr(
            self.dashboard_page,
            "refresh",
        ):
            self.dashboard_page.refresh()

        self.statusBar().showMessage(
            (
                f"Analysis completed: "
                f"{investigation.report_name}"
            )
        )

    def _create_status_bar(self) -> None:
        """
        Create the application status bar.
        """

        self.statusBar().showMessage(
            "SOC-IQ Ready"
        )