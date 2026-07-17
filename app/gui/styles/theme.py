"""
Application theme for the SOC-IQ desktop GUI.

This module provides the global Qt stylesheet used by the application.
"""

from __future__ import annotations


def get_stylesheet() -> str:
    """
    Return the application's global stylesheet.
    """

    return """
    /* ============================
       Global
       ============================ */

    QWidget {
        background-color: #1E1E1E;
        color: #F0F0F0;
        font-family: "Segoe UI";
        font-size: 10pt;
    }

    /* ============================
       Menu Bar
       ============================ */

    QMenuBar {
        background-color: #252526;
        border-bottom: 1px solid #3C3C3C;
    }

    QMenuBar::item {
        padding: 6px 12px;
    }

    QMenuBar::item:selected {
        background-color: #3E3E42;
    }

    /* ============================
       Menu
       ============================ */

    QMenu {
        background-color: #2D2D30;
        border: 1px solid #3C3C3C;
    }

    QMenu::item {
        padding: 6px 24px;
    }

    QMenu::item:selected {
        background-color: #007ACC;
    }

    /* ============================
       Tool Bar
       ============================ */

    QToolBar {
        background-color: #252526;
        border: none;
        spacing: 6px;
        padding: 6px;
    }

    /* ============================
       Push Buttons
       ============================ */

    QPushButton {
        background-color: #2D2D30;
        border: 1px solid #3C3C3C;
        border-radius: 6px;
        padding: 10px;
        text-align: left;
    }

    QPushButton:hover {
        background-color: #3E3E42;
    }

    QPushButton:pressed {
        background-color: #007ACC;
    }

    /* ============================
       Labels
       ============================ */

    QLabel {
        background: transparent;
    }

    /* ============================
       Status Bar
       ============================ */

    QStatusBar {
        background-color: #252526;
        border-top: 1px solid #3C3C3C;
    }

    /* ============================
       Stacked Widget
       ============================ */

    QStackedWidget {
        background-color: #1E1E1E;
    }
    """