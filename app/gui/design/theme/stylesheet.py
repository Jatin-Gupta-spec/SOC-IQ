"""
SOC-IQ Design System
Global Application Stylesheet

Builds the application's global Qt stylesheet using the
Design System and reusable stylesheet builder.
"""

from __future__ import annotations

from app.gui.design.theme.palette import DEFAULT_PALETTE
from app.gui.design.theme.stylesheet_builder import StylesheetBuilder


class Stylesheet:
    """
    Builds the global application stylesheet.
    """

    def __init__(self) -> None:
        self._builder = StylesheetBuilder(DEFAULT_PALETTE)

    def build(self) -> str:
        """
        Build the complete application stylesheet.
        """

        parts = [
            self._base(),
            self._builder.button_primary(),
            self._builder.line_edit(),
            self._builder.card(),
            self._scrollbars(),
            self._tables(),
            self._headers(),
            self._menus(),
            self._toolbar(),
            self._tooltip(),
        ]

        return "\n\n".join(parts)

    def _base(self) -> str:
        """
        Base application styling shared across all widgets.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QWidget {{
            background-color: {palette.background_primary};
            color: {palette.text_primary};
        }}

        QLabel {{
            color: {palette.text_primary};
            background: transparent;
        }}
        """.strip()

    def _scrollbars(self) -> str:
        """
        Themed scrollbars. Native scrollbars are the fastest way
        to make a dark UI look unfinished if left unstyled.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 2px 0px 2px 0px;
        }}

        QScrollBar::handle:vertical {{
            background: {palette.surface_secondary};
            border: 1px solid {palette.border_default};
            border-radius: 5px;
            min-height: 32px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {palette.border_strong};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
            border: none;
        }}

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 12px;
            margin: 0px 2px 0px 2px;
        }}

        QScrollBar::handle:horizontal {{
            background: {palette.surface_secondary};
            border: 1px solid {palette.border_default};
            border-radius: 5px;
            min-width: 32px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {palette.border_strong};
        }}

        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0px;
            background: none;
            border: none;
        }}

        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
        """.strip()

    def _tables(self) -> str:
        """
        QTableView / QTableWidget: selection, alternate rows, hover.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QTableView, QTableWidget {{
            background-color: {palette.surface_primary};
            alternate-background-color: {palette.background_secondary};
            gridline-color: transparent;
            border: 1px solid {palette.border_default};
            border-radius: 8px;
            selection-background-color: {palette.surface_elevated};
            selection-color: {palette.text_primary};
            outline: none;
        }}

        QTableView::item, QTableWidget::item {{
            padding: 8px 10px;
            border: none;
        }}

        QTableView::item:hover, QTableWidget::item:hover {{
            background-color: {palette.surface_secondary};
        }}

        QTableView::item:selected, QTableWidget::item:selected {{
            background-color: {palette.surface_elevated};
            color: {palette.text_primary};
        }}
        """.strip()

    def _headers(self) -> str:
        """
        Table header sections.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QHeaderView::section {{
            background-color: {palette.background_secondary};
            color: {palette.text_muted};
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {palette.border_default};
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        QHeaderView::section:horizontal {{
            border-right: 1px solid {palette.border_subtle};
        }}

        QHeaderView::section:last {{
            border-right: none;
        }}

        QTableCornerButton::section {{
            background-color: {palette.background_secondary};
            border: none;
        }}
        """.strip()

    def _menus(self) -> str:
        """
        Menu bar and dropdown menus.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QMenuBar {{
            background-color: {palette.background_secondary};
            color: {palette.text_secondary};
            border-bottom: 1px solid {palette.border_default};
            padding: 2px 4px;
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 6px 12px;
            border-radius: 6px;
        }}

        QMenuBar::item:selected {{
            background-color: {palette.surface_secondary};
            color: {palette.text_primary};
        }}

        QMenu {{
            background-color: {palette.surface_elevated};
            color: {palette.text_primary};
            border: 1px solid {palette.border_default};
            border-radius: 8px;
            padding: 6px;
        }}

        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 6px;
        }}

        QMenu::item:selected {{
            background-color: {palette.surface_secondary};
            color: {palette.text_primary};
        }}

        QMenu::separator {{
            height: 1px;
            background: {palette.border_subtle};
            margin: 6px 8px;
        }}
        """.strip()

    def _toolbar(self) -> str:
        """
        Application toolbar.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QToolBar {{
            background-color: {palette.background_secondary};
            border: none;
            border-bottom: 1px solid {palette.border_default};
            padding: 6px 10px;
            spacing: 6px;
        }}

        QToolBar QToolButton {{
            background: transparent;
            color: {palette.text_secondary};
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid transparent;
        }}

        QToolBar QToolButton:hover {{
            background-color: {palette.surface_secondary};
            color: {palette.text_primary};
            border: 1px solid {palette.border_default};
        }}

        QToolBar QToolButton:pressed {{
            background-color: {palette.surface_elevated};
        }}
        """.strip()

    def _tooltip(self) -> str:
        """
        Tooltips.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QToolTip {{
            background-color: {palette.surface_elevated};
            color: {palette.text_primary};
            border: 1px solid {palette.border_default};
            border-radius: 6px;
            padding: 6px 10px;
        }}
        """.strip()


DEFAULT_STYLESHEET = Stylesheet()