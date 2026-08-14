"""
SOC-IQ Design System

Metric Card

Enterprise KPI card built on top of ModernCard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Radius, Spacing


class MetricCard(ModernCard):
    """
    Enterprise KPI card.

    Displays:

    • Icon (optional)
    • Title
    • Value
    • Subtitle
    • Footer
    • Optional badge
    """

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        footer: str = "",
        parent: QWidget | None = None,
    ) -> None:

        self._icon_label = QLabel()
        self._icon_label.setFixedWidth(20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label = QLabel(title)
        self._value_label = QLabel(value)
        self._subtitle_label = QLabel(subtitle)

        self._footer_label = QLabel(footer)
        self._badge_label = QLabel()

        # Fixed-height spacer WIDGET (not addSpacing()) placed
        # directly before the footer label, so its visibility can
        # be toggled in lockstep with the footer's. A bare
        # layout.addSpacing() call ignores widget visibility and
        # always reserves its space -- that's what previously left
        # a permanent Spacing.SM gap above the footer even though
        # every current caller leaves footer empty/hidden.
        self._footer_spacer = QWidget()
        self._footer_spacer.setFixedHeight(Spacing.SM)

        # Root cause of KPI text clipping (e.g. "Critical
        # Investigations", "SQLite Database"): these labels never
        # wrapped, so at narrow card widths (~1280x720, 1100x700)
        # the text simply overflowed the card's allocated column
        # width and got clipped. Word wrap lets Qt's layout shrink
        # each label down to its natural minimum (the widest single
        # word) and grow the card's own height to fit -- no fixed
        # height, no truncation.
        self._title_label.setWordWrap(True)
        self._subtitle_label.setWordWrap(True)
        self._footer_label.setWordWrap(True)

        self._icon_label.hide()
        self._badge_label.hide()

        super().__init__(parent)

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_contents(self) -> None:
        """
        Build the card's internal layout.

        All content is assembled into one local `card_layout`
        (spacing explicitly set to 0) which is then added to
        ModernCard's `content_layout()` via a single addLayout()
        call. ModernCard's content_layout() already applies
        Spacing.CONTENT_GAP between every item added directly to
        it -- the previous version added header/spacer/value/
        spacer/subtitle/stretch/spacer/footer as separate items
        straight onto that layout, so the automatic gap compounded
        with every manual addSpacing() call between them, inflating
        real on-screen gaps well past the token values used. Since
        content_layout() now only ever receives this one local
        layout as a single item, its own spacing never enters the
        picture -- every gap inside the card is controlled purely
        by the addSpacing() calls below, at exactly their token
        values.
        """

        card_layout = QVBoxLayout()
        card_layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(Spacing.XS)

        header.addWidget(self._icon_label)
        header.addWidget(self._title_label)
        header.addStretch()
        header.addWidget(self._badge_label)

        card_layout.addLayout(header)

        card_layout.addSpacing(Spacing.SM)

        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._footer_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        card_layout.addWidget(self._value_label)

        # Subtitle and footer are always added to the layout (not
        # only when they start non-empty) so that set_subtitle()/
        # set_footer() work correctly even when called after
        # construction. Visibility — not layout membership — is
        # what controls whether they take up space; Qt layouts
        # skip hidden widgets automatically. (The footer's
        # preceding gap is a widget -- self._footer_spacer -- for
        # exactly this reason too; see its creation in __init__.)

        card_layout.addSpacing(Spacing.XS)

        self._subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._subtitle_label.setVisible(
            bool(self._subtitle_label.text())
        )

        card_layout.addWidget(
            self._subtitle_label
        )

        card_layout.addStretch()

        self._footer_spacer.setVisible(
            bool(self._footer_label.text())
        )

        card_layout.addWidget(self._footer_spacer)

        self._footer_label.setVisible(
            bool(self._footer_label.text())
        )

        card_layout.addWidget(
            self._footer_label
        )

        self.content_layout().addLayout(card_layout)

    @staticmethod
    def _tinted(hex_color: str, alpha: int) -> str:
        """
        Return an rgba() string for the given hex color at
        the given alpha (0-255), for use in QSS.

        Mirrors StatusBadge._tinted() so the badge here reads
        as the same restrained tinted-pill treatment used
        elsewhere in the design system, without importing from
        or modifying StatusBadge itself.
        """

        color = QColor(hex_color)

        return (
            f"rgba({color.red()}, {color.green()}, "
            f"{color.blue()}, {alpha})"
        )

    def refresh_theme(self) -> None:

        palette = self.palette
        fonts = self.fonts

        self._icon_label.setFont(
            fonts.heading()
        )

        self._title_label.setFont(
            fonts.label()
        )

        self._value_label.setFont(
            fonts.display()
        )

        self._subtitle_label.setFont(
            fonts.body_small()
        )

        self._footer_label.setFont(
            fonts.caption()
        )

        self._badge_label.setFont(
            fonts.caption()
        )

        self._icon_label.setStyleSheet(
            f"color:{palette.text_primary};"
        )

        self._title_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        self._value_label.setStyleSheet(
            f"color:{palette.text_primary};"
        )

        self._subtitle_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        self._footer_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        accent = palette.brand_primary
        badge_tint = self._tinted(accent, alpha=32)
        badge_border = self._tinted(accent, alpha=90)

        self._badge_label.setStyleSheet(
            f"""
            color:{accent};
            background-color:{badge_tint};
            border: 1px solid {badge_border};
            font-weight: 600;
            padding: {Spacing.XXS}px {Spacing.SM}px;
            border-radius: {Radius.BADGE}px;
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_icon(self, icon: str) -> None:
        """
        Sets the KPI icon displayed beside the title.
        """
        self._icon_label.setText(icon)
        self._icon_label.setVisible(bool(icon))

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def set_footer(self, footer: str) -> None:
        self._footer_label.setText(footer)
        has_footer = bool(footer)
        self._footer_label.setVisible(has_footer)
        self._footer_spacer.setVisible(has_footer)

    def set_badge(self, text: str) -> None:
        self._badge_label.setText(text)
        self._badge_label.setVisible(bool(text))

    def clear_badge(self) -> None:
        self._badge_label.clear()
        self._badge_label.hide()