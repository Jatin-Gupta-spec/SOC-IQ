"""
SOC-IQ Design System
Global Application Stylesheet

Builds the application's global Qt stylesheet using the
Design System and reusable stylesheet builder.
"""

from __future__ import annotations

from app.gui.design.theme.palette import DEFAULT_PALETTE
from app.gui.design.theme.stylesheet_builder import StylesheetBuilder
from app.gui.design.tokens import Radius, Spacing, Typography


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
            self._default_button(),
            self._builder.line_edit(),
            self._builder.card(),
            self._page_container(),
            self._section_header(),
            self._panel(),
            self._badge(),
            self._key_value(),
            self._dashboard_empty_state(),
            self._summary_card(),
            self._scrollbars(),
            self._tables(),
            self._headers(),
            self._menus(),
            self._toolbar(),
            self._status_bar(),
            self._stacked_widget(),
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

    def _default_button(self) -> str:
        """
        Default styling for the bare `QPushButton` selector.

        Deliberately NOT `StylesheetBuilder.button_primary()` —
        that fragment fills the button with `palette.brand_primary`
        (now purple), which would make every generic button in the
        app read as a primary CTA.

        This only affects a plain `QPushButton` used directly,
        outside of `AnimatedButton`. `AnimatedButton` sets its own
        per-variant stylesheet directly on its internal QPushButton
        instance via `setStyleSheet()`, which takes precedence over
        this application-level rule for that widget — so this
        neutral default and AnimatedButton's PRIMARY/SECONDARY/
        OUTLINE/DANGER variants do not conflict. See
        animated_button.py.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QPushButton {{
            background-color: {palette.surface_secondary};
            color: {palette.text_primary};
            border: 1px solid {palette.border_default};
            border-radius: {Radius.BUTTON}px;
            padding: {Spacing.SM}px {Spacing.MD}px;
        }}

        QPushButton:hover {{
            background-color: {palette.surface_elevated};
            border: 1px solid {palette.border_strong};
        }}

        QPushButton:pressed {{
            background-color: {palette.surface_primary};
        }}

        QPushButton:disabled {{
            color: {palette.text_disabled};
            background-color: {palette.surface_secondary};
            border: 1px solid transparent;
        }}
        """.strip()

    def _page_container(self) -> str:
        """
        PageContainer chrome: the transparent wrapping frame plus
        its title/description labels.

        Migrated from the legacy theme.py selectors
        `QFrame#pageContainer`, `QLabel#pageTitle`,
        `QLabel#pageDescription`. `PageContainer` itself
        (page_container.py) is unchanged — it only sets these
        objectNames, so styling continues to apply without any
        widget code changes.
        """

        palette = DEFAULT_PALETTE
        title = Typography.HEADING
        description = Typography.BODY

        return f"""
        QFrame#pageContainer {{
            background-color: transparent;
            border: none;
        }}

        QLabel#pageTitle {{
            font-size: {title.size}pt;
            font-weight: {title.weight};
            color: {palette.text_primary};
        }}

        QLabel#pageDescription {{
            font-size: {description.size}pt;
            color: {palette.text_muted};
        }}
        """.strip()

    def _section_header(self) -> str:
        """
        SectionHeader chrome, migrated from the legacy
        `QLabel#sectionHeaderTitle` / `QLabel#sectionHeaderDescription`
        selectors. `SectionHeader` (section_header.py) only sets
        these objectNames, so it needs no code changes.
        """

        palette = DEFAULT_PALETTE
        title = Typography.TITLE
        description = Typography.BODY

        return f"""
        QLabel#sectionHeaderTitle {{
            font-size: {title.size}pt;
            font-weight: {title.weight};
            color: {palette.text_primary};
        }}

        QLabel#sectionHeaderDescription {{
            font-size: {description.size}pt;
            color: {palette.text_muted};
        }}
        """.strip()

    def _panel(self) -> str:
        """
        The shared `Panel` container (panel.py), object name
        "panel". Distinct from `StylesheetBuilder.card()`'s
        `QFrame#legacyCard`, which is a separate opt-in fragment
        for legacy direct consumers.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QFrame#panel {{
            background-color: {palette.surface_primary};
            border: 1px solid {palette.border_default};
            border-radius: {Radius.PANEL}px;
        }}

        QFrame#panel:hover {{
            border: 1px solid {palette.border_strong};
        }}
        """.strip()

    def _badge(self) -> str:
        """
        Small status/label pill, object name "badge". Migrated
        from the legacy `QLabel#badge` selector; now uses the
        brand accent (purple) instead of the old hardcoded blue.

        Radius stays a literal 10px: no Radius token equals 10
        (SM=4, MD=6, LG=8, XL=12, XXL=16), and approximating to
        the nearest token was explicitly rejected in favor of
        preserving the exact original value.
        """

        palette = DEFAULT_PALETTE
        label = Typography.LABEL

        return f"""
        QLabel#badge {{
            background-color: {palette.brand_primary};
            color: {palette.text_primary};
            border: none;
            border-radius: 10px;
            padding: {Spacing.XS}px {Spacing.MD}px;
            font-size: {label.size}pt;
            font-weight: {label.weight};
        }}
        """.strip()

    def _key_value(self) -> str:
        """
        Key/value label pairs, migrated from the legacy
        `QLabel#keyValueKey` / `QLabel#keyValueValue` selectors.
        """

        palette = DEFAULT_PALETTE
        key = Typography.LABEL
        value = Typography.BODY

        return f"""
        QLabel#keyValueKey {{
            color: {palette.text_muted};
            font-size: {key.size}pt;
            font-weight: {key.weight};
        }}

        QLabel#keyValueValue {{
            color: {palette.text_primary};
            font-size: {value.size}pt;
            font-weight: 600;
        }}
        """.strip()

    def _dashboard_empty_state(self) -> str:
        """
        Empty-state placeholder shown on the dashboard, migrated
        from the legacy `QLabel#dashboardEmptyState` selector.

        Radius stays a literal 10px for the same reason as badge()
        above — no exact Radius token exists for it.
        """

        palette = DEFAULT_PALETTE
        body = Typography.BODY

        return f"""
        QLabel#dashboardEmptyState {{
            background-color: {palette.surface_secondary};
            border: 1px solid {palette.border_default};
            border-radius: 10px;
            padding: {Spacing.XL}px;
            font-size: {body.size}pt;
            color: {palette.text_muted};
        }}
        """.strip()

    def _summary_card(self) -> str:
        """
        Dashboard summary/stat cards, migrated from the legacy
        `QFrame#summaryCard` + child label selectors. Hover accent
        and trend color now come from the brand/status tokens
        instead of hardcoded hex.
        """

        palette = DEFAULT_PALETTE
        title = Typography.LABEL
        value = Typography.DISPLAY
        subtitle = Typography.BODY
        footer = Typography.CAPTION
        trend = Typography.CAPTION

        return f"""
        QFrame#summaryCard {{
            background-color: {palette.surface_elevated};
            border: 1px solid {palette.border_subtle};
            border-radius: {Radius.XXL}px;
        }}

        QFrame#summaryCard:hover {{
            background-color: {palette.surface_secondary};
            border: 1px solid {palette.brand_primary};
        }}

        QLabel#summaryCardTitle {{
            font-size: {title.size}pt;
            font-weight: 700;
            color: {palette.text_secondary};
            text-transform: uppercase;
        }}

        QLabel#summaryCardValue {{
            font-size: {value.size}pt;
            font-weight: 800;
            color: {palette.text_primary};
        }}

        QLabel#summaryCardSubtitle {{
            font-size: {subtitle.size}pt;
            color: {palette.info};
        }}

        QLabel#summaryCardFooter {{
            font-size: {footer.size}pt;
            color: {palette.text_muted};
        }}

        QLabel#summaryCardTrend {{
            font-size: {trend.size}pt;
            font-weight: 600;
            color: {palette.success};
        }}
        """.strip()

    def _status_bar(self) -> str:
        """
        Application status bar, migrated from the legacy
        `QStatusBar` selector.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QStatusBar {{
            background-color: {palette.background_secondary};
            border-top: 1px solid {palette.border_default};
        }}
        """.strip()

    def _stacked_widget(self) -> str:
        """
        Page-hosting stacked widget, migrated from the legacy
        `QStackedWidget` selector.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QStackedWidget {{
            background-color: {palette.background_primary};
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

        Padding tightened from Spacing.SM/`10px` to Spacing.XS/
        Spacing.SM (4px/8px) on both the bar and its buttons. The
        toolbar's height is now pinned explicitly in
        `MainWindow._create_tool_bar()` via `Spacing.TOOLBAR_HEIGHT`
        and a reduced icon size; this padding reduction is the
        matching QSS-level change so the "Analyze" band reads as an
        intentional, compact bar rather than a large mostly-empty
        one.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QToolBar {{
            background-color: {palette.background_secondary};
            border: none;
            border-bottom: 1px solid {palette.border_default};
            padding: {Spacing.XS}px {Spacing.SM}px;
            spacing: {Spacing.XS}px;
        }}

        QToolBar QToolButton {{
            background: transparent;
            color: {palette.text_secondary};
            padding: {Spacing.XS}px {Spacing.SM}px;
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