"""
SOC-IQ Dashboard Component

Animated Metric Card Widget

Enterprise Metric Card with animated numerical counter transitions, trend pill indicators,
and dynamic hover elevation effects.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.status_badge import BadgeType, StatusBadge
from app.gui.design.tokens import Radius, Spacing


class AnimatedMetricCard(ModernCard):
    """
    KPI Metric card with numerical animation and trend indicators.
    """

    def __init__(
        self,
        title: str,
        value: int = 0,
        subtitle: str = "",
        trend_text: str = "",
        trend_type: BadgeType = BadgeType.INFO,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = title
        self._target_value = value
        self._display_value = 0
        self._subtitle = subtitle

        self._title_label = QLabel(title)
        self._value_label = QLabel("0")
        self._subtitle_label = QLabel(subtitle)
        self._trend_badge = StatusBadge(trend_text, trend_type) if trend_text else None

        self._anim = QPropertyAnimation(self, b"animated_value", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._build_card_ui()
        if value > 0:
            self.set_animated_value_target(value)

    # Property for QPropertyAnimation
    def get_animated_value(self) -> int:
        return self._display_value

    def set_animated_value(self, val: int) -> None:
        self._display_value = int(val)
        self._value_label.setText(f"{self._display_value:,}")

    animated_value = Property(int, get_animated_value, set_animated_value)

    def set_animated_value_target(self, target: int) -> None:
        """
        Animate numerical value to target integer.
        """
        self._target_value = target
        self._anim.stop()
        self._anim.setStartValue(self._display_value)
        self._anim.setEndValue(target)
        self._anim.start()

    def set_value_str(self, val_str: str) -> None:
        """
        Set non-numeric value or format string.
        """
        try:
            val_int = int(val_str)
            self.set_animated_value_target(val_int)
        except ValueError:
            self._value_label.setText(val_str)

    def _build_card_ui(self) -> None:
        """
        Construct card layout.
        """
        palette = self.theme.palette
        fonts = self.theme.fonts

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        main_layout.setSpacing(Spacing.SM)

        # Header Row: Title & Trend Badge
        header_row = QHBoxLayout()
        self._title_label.setFont(fonts.caption())
        self._title_label.setStyleSheet(
            f"color: {palette.text_muted}; text-transform: uppercase; font-weight: 600; letter-spacing: 0.8px;"
        )
        header_row.addWidget(self._title_label)
        header_row.addStretch()

        if self._trend_badge is not None:
            header_row.addWidget(self._trend_badge)

        main_layout.addLayout(header_row)

        # Numeric Value
        self._value_label.setFont(fonts.display())
        self._value_label.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 800; font-size: 32px;"
        )
        main_layout.addWidget(self._value_label)

        # Subtitle
        self._subtitle_label.setFont(fonts.caption())
        self._subtitle_label.setStyleSheet(f"color: {palette.text_secondary};")
        main_layout.addWidget(self._subtitle_label)

        self.add_layout(main_layout)

    def enterEvent(self, event) -> None:
        """
        Hover border glow effect.
        """
        palette = self.theme.palette
        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_secondary};
                border: 1px solid {palette.accent};
                border-radius: {Radius.CARD}px;
            }}
            """
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """
        Reset default style on mouse leave.
        """
        palette = self.theme.palette
        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface};
                border: 1px solid {palette.border_subtle};
                border-radius: {Radius.CARD}px;
            }}
            """
        )
        super().leaveEvent(event)
