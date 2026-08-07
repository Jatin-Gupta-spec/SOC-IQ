"""
SOC-IQ Design System
Status Badge

Reusable badge component for displaying statuses and severity levels.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class BadgeType(Enum):
    """Supported badge variants."""

    DEFAULT = auto()

    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    INFO = auto()

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class StatusBadge(BaseWidget):
    """
    Reusable status badge.

    Displays a short piece of text using semantic
    colours from the active theme.

    Rendered as a tinted-fill pill (low-opacity background,
    full-opacity text/border in the semantic color) rather
    than a solid-fill chip — this reads as enterprise UI
    rather than a consumer-app tag, and stays legible when
    many badges appear together in a table.
    """

    def __init__(
        self,
        text: str,
        badge_type: BadgeType = BadgeType.DEFAULT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._badge_type = badge_type

        self._label = QLabel(text)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._build_ui()
        self.refresh_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            Spacing.SM,
            Spacing.XS,
            Spacing.SM,
            Spacing.XS,
        )

        layout.setSpacing(0)

        layout.addWidget(self._label)

        self.setMinimumHeight(24)

        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )

    def _apply_theme(self) -> None:
        fonts = self.fonts

        self._label.setFont(fonts.label())

        accent = self._badge_accent_color()
        tint = self._tinted(accent, alpha=32)

        self.setStyleSheet(
            f"""
            StatusBadge {{
                background-color: {tint};
                border: 1px solid {self._tinted(accent, alpha=90)};
                border-radius: {Radius.BADGE}px;
            }}

            QLabel {{
                color: {accent};
                font-weight: 600;
                background: transparent;
            }}
            """
        )

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    def _badge_accent_color(self) -> str:
        """
        Return the single semantic accent color for the
        current badge type (used for both text and, tinted,
        the background/border).
        """

        palette = self.palette

        mapping = {
            BadgeType.DEFAULT: palette.text_secondary,
            BadgeType.SUCCESS: palette.success,
            BadgeType.WARNING: palette.warning,
            BadgeType.ERROR: palette.error,
            BadgeType.INFO: palette.info,
            BadgeType.LOW: palette.severity_low,
            BadgeType.MEDIUM: palette.severity_medium,
            BadgeType.HIGH: palette.severity_high,
            BadgeType.CRITICAL: palette.severity_critical,
        }

        return mapping[self._badge_type]

    @staticmethod
    def _tinted(hex_color: str, alpha: int) -> str:
        """
        Return an rgba() string for the given hex color at
        the given alpha (0-255), for use in QSS.
        """

        color = QColor(hex_color)

        return (
            f"rgba({color.red()}, {color.green()}, "
            f"{color.blue()}, {alpha})"
        )

    def refresh_theme(self) -> None:
        """
        Refresh the badge styling.
        """

        self._apply_theme()

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_text(self, text: str) -> None:
        """Update the badge text."""
        self._label.setText(text)

    def text(self) -> str:
        """Return the badge text."""
        return self._label.text()

    def set_badge_type(self, badge_type: BadgeType) -> None:
        """Update the badge type."""
        self._badge_type = badge_type
        self.refresh_theme()

    def badge_type(self) -> BadgeType:
        """Return the current badge type."""
        return self._badge_type