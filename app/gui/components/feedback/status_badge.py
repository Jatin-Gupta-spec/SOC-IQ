"""
SOC-IQ Design System
Status Badge

Reusable badge component for displaying statuses and severity levels.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt
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
        self._apply_theme()

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

        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._label.setFont(fonts.label())

        background, foreground = self._badge_colors()

        self.setStyleSheet(
            f"""
            StatusBadge {{
                background-color: {background};
                border-radius: {Radius.BADGE}px;
            }}

            QLabel {{
                color: {foreground};
                background: transparent;
            }}
            """
        )

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    def _badge_colors(self) -> tuple[str, str]:
        palette = self.theme.palette

        mapping = {
            BadgeType.DEFAULT: (
                palette.surface_secondary,
                palette.text_primary,
            ),
            BadgeType.SUCCESS: (
                palette.success,
                palette.text_primary,
            ),
            BadgeType.WARNING: (
                palette.warning,
                palette.text_primary,
            ),
            BadgeType.ERROR: (
                palette.error,
                palette.text_primary,
            ),
            BadgeType.INFO: (
                palette.info,
                palette.text_primary,
            ),
            BadgeType.LOW: (
                palette.severity_low,
                palette.text_primary,
            ),
            BadgeType.MEDIUM: (
                palette.severity_medium,
                palette.text_primary,
            ),
            BadgeType.HIGH: (
                palette.severity_high,
                palette.text_primary,
            ),
            BadgeType.CRITICAL: (
                palette.severity_critical,
                palette.text_primary,
            ),
        }

        return mapping[self._badge_type]

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
        self._apply_theme()

    def badge_type(self) -> BadgeType:
        """Return the current badge type."""
        return self._badge_type