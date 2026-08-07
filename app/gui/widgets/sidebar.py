"""
Sidebar widget for the SOC-IQ desktop application.

This module contains the application's primary navigation panel.
The widget is responsible only for presenting navigation buttons
and notifying other components when a button is selected.
"""

from __future__ import annotations

from enum import IntEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.design.tokens import Spacing

from app.gui.design.theme.theme_manager import theme_manager


class NavigationPage(IntEnum):
    """
    Application page indexes.

    Mirrors the order pages are added to MainWindow's
    QStackedWidget. WORKSPACE and COMPONENT_SHOWCASE have no
    sidebar button — they're opened programmatically — but are
    included here so every part of the app shares one source of
    truth for page indices instead of hardcoding raw integers.
    """

    DASHBOARD = 0
    ANALYZE = 1
    IOC_VIEWER = 2
    THREAT_INTELLIGENCE = 3
    RISK_DASHBOARD = 4
    HISTORY = 5
    SETTINGS = 6
    WORKSPACE = 7
    COMPONENT_SHOWCASE = 8


class SidebarWidget(QWidget):
    """
    Sidebar navigation widget.
    """

    page_selected = Signal(int)

    def __init__(self) -> None:
        super().__init__()

        self.setFixedWidth(240)

        self._buttons: dict[int, QPushButton] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the sidebar user interface.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.SM)

        title = QLabel("SOC-IQ")

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet(
            f"""
            color: {theme_manager.palette.text_primary};
            font-size: 20px;
            font-weight: 700;
            padding-bottom: 12px;
            """
        )

        layout.addWidget(title)

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

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            button.clicked.connect(
                lambda checked=False, page_index=int(page):
                    self.page_selected.emit(page_index)
            )

            layout.addWidget(button)

            self._buttons[int(page)] = button

        layout.addStretch()

        self.setLayout(layout)

        # Highlight Dashboard by default — MainWindow adds it as
        # page 0, and it's the page shown on startup.
        self.set_active_page(NavigationPage.DASHBOARD)

    # --------------------------------------------------
    # Active state
    # --------------------------------------------------

    def _apply_button_style(
        self,
        button: QPushButton,
        active: bool,
    ) -> None:
        """
        Style a single navigation button for its active state.
        """

        palette = theme_manager.palette

        if active:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    border-left: 3px solid {palette.brand_primary};
                    background-color: {palette.surface_elevated};
                    color: {palette.text_primary};
                    font-weight: 600;
                }}
                """
            )
        else:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    border-left: 3px solid transparent;
                    background-color: transparent;
                    color: {palette.text_secondary};
                    font-weight: 400;
                }}

                QPushButton:hover {{
                    background-color: {palette.surface_elevated};
                    color: {palette.text_primary};
                }}
                """
            )

    def set_active_page(
        self,
        page_index: int,
    ) -> None:
        """
        Highlight the button for the currently active page.

        Pages without a sidebar button (e.g. the Investigation
        Workspace) simply leave every button unhighlighted.
        """

        for index, button in self._buttons.items():
            self._apply_button_style(
                button,
                active=(index == int(page_index)),
            )