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
    /* ==========================================================
       GLOBAL
       ========================================================== */

    QWidget {
        background-color: #1E1E1E;
        color: #F3F4F6;
        font-family: "Segoe UI";
        font-size: 10pt;
    }

    QLabel {
        background: transparent;
    }

    /* ==========================================================
       MENU BAR
       ========================================================== */

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

    /* ==========================================================
       MENUS
       ========================================================== */

    QMenu {
        background-color: #252526;
        border: 1px solid #3C3C3C;
    }

    QMenu::item {
        padding: 6px 24px;
    }

    QMenu::item:selected {
        background-color: #007ACC;
    }

    /* ==========================================================
       TOOL BAR
       ========================================================== */

    QToolBar {
        background-color: #252526;
        border: none;
        spacing: 6px;
        padding: 6px;
    }

    /* ==========================================================
       PUSH BUTTONS
       ========================================================== */

    QPushButton {
        background-color: #2D2D30;
        border: 1px solid #3C3C3C;
        border-radius: 8px;
        padding: 10px;
        text-align: left;
    }

    QPushButton:hover {
        background-color: #3E3E42;
    }

    QPushButton:pressed {
        background-color: #007ACC;
    }

    QPushButton:disabled {
        color: #808080;
        background-color: #252526;
    }

    /* ==========================================================
       PAGE CONTAINER
       ========================================================== */

    QFrame#pageContainer {
        background-color: transparent;
        border: none;
    }

    QLabel#pageTitle {
        font-size: 22pt;
        font-weight: 700;
        color: #FFFFFF;
    }

    QLabel#pageDescription {
        font-size: 10pt;
        color: #A1A1AA;
        margin-bottom: 10px;
    }

    /* ==========================================================
       SECTION HEADER
       ========================================================== */

    QLabel#sectionHeaderTitle {
        font-size: 15pt;
        font-weight: 600;
        color: #FFFFFF;
    }

    QLabel#sectionHeaderDescription {
        font-size: 10pt;
        color: #A1A1AA;
    }

    /* ==========================================================
       PANEL
       ========================================================== */

    QFrame#panel {
        background-color: #252526;
        border: 1px solid #3C3C3C;
        border-radius: 12px;
    }

    QFrame#panel:hover {
        border: 1px solid #4A4A4A;
    }

    /* ==========================================================
       BADGE
       ========================================================== */

    QLabel#badge {
        background-color: #0E639C;
        color: #FFFFFF;
        border: none;
        border-radius: 10px;
        padding: 4px 12px;
        font-size: 9pt;
        font-weight: 600;
    }

    /* ==========================================================
       KEY VALUE ROW
       ========================================================== */

    QLabel#keyValueKey {
        color: #A1A1AA;
        font-size: 10pt;
        font-weight: 500;
    }

    QLabel#keyValueValue {
        color: #FFFFFF;
        font-size: 10pt;
        font-weight: 600;
    }

    /* ==========================================================
       DASHBOARD
       ========================================================== */

    QLabel#dashboardEmptyState {
        background-color: #252526;
        border: 1px solid #3C3C3C;
        border-radius: 10px;
        padding: 24px;
        font-size: 10pt;
        color: #BDBDBD;
    }

    /* ==========================================================
       SUMMARY CARD
       ========================================================== */

    QFrame#summaryCard {
        background-color: #252526;
        border: 1px solid #3C3C3C;
        border-radius: 12px;
    }

    QFrame#summaryCard:hover {
        border: 1px solid #007ACC;
    }

    QLabel#summaryCardTitle {
        font-size: 11pt;
        font-weight: 600;
        color: #D4D4D4;
    }

    QLabel#summaryCardValue {
        font-size: 28pt;
        font-weight: 700;
        color: #FFFFFF;
    }

    QLabel#summaryCardSubtitle {
        font-size: 10pt;
        color: #4FC3F7;
    }

    QLabel#summaryCardFooter {
        font-size: 9pt;
        color: #A1A1AA;
    }

    /* ==========================================================
       STATUS BAR
       ========================================================== */

    QStatusBar {
        background-color: #252526;
        border-top: 1px solid #3C3C3C;
    }

    /* ==========================================================
       STACKED WIDGET
       ========================================================== */

    QStackedWidget {
        background-color: #1E1E1E;
    }
    """