"""
SOC-IQ Design System

Metric Card

Enterprise KPI card built on top of ModernCard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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

        self._icon_label.hide()
        self._badge_label.hide()

        super().__init__(parent)

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_contents(self) -> None:

        layout = self.content_layout()

        header = QHBoxLayout()
        header.setSpacing(Spacing.XS)

        header.addWidget(self._icon_label)
        header.addWidget(self._title_label)
        header.addStretch()
        header.addWidget(self._badge_label)

        layout.addLayout(header)

        layout.addSpacing(Spacing.SM)

        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._footer_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(self._value_label)

        # Subtitle and footer are always added to the layout (not
        # only when they start non-empty) so that set_subtitle()/
        # set_footer() work correctly even when called after
        # construction. Visibility — not layout membership — is
        # what controls whether they take up space; Qt layouts
        # skip hidden widgets automatically.

        layout.addSpacing(Spacing.XS)

        self._subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._subtitle_label.setVisible(
            bool(self._subtitle_label.text())
        )

        layout.addWidget(
            self._subtitle_label
        )

        layout.addStretch()

        layout.addSpacing(Spacing.SM)

        self._footer_label.setVisible(
            bool(self._footer_label.text())
        )

        layout.addWidget(
            self._footer_label
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

        self._badge_label.setStyleSheet(
            f"""
            color:{palette.text_primary};
            background:{palette.accent};
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
        self._footer_label.setVisible(bool(footer))

    def set_badge(self, text: str) -> None:
        self._badge_label.setText(text)
        self._badge_label.setVisible(bool(text))

    def clear_badge(self) -> None:
        self._badge_label.clear()
        self._badge_label.hide()