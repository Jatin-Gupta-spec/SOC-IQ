"""
SOC-IQ Design System
Status Badge

Reusable badge component for displaying statuses and severity levels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QHBoxLayout, QSizePolicy, QWidget

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing

# Canonical definition lives in app.services.models so that backend
# services can describe badge/severity types without importing GUI
# code. Re-exported here (same object, same members) for backward
# compatibility with existing GUI imports.
from app.services.models import BadgeType

__all__ = ["BadgeType", "StatusBadge"]


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

        # Root cause of P0-2 (hero badge/timestamp collision): this used
        # to be `self.setSizePolicy(self.sizePolicy().horizontalPolicy(),
        # self.sizePolicy().verticalPolicy())` -- a no-op that just read
        # back and reapplied QWidget's existing default policy
        # (Preferred/Preferred). Preferred lets Qt shrink the badge below
        # its natural text width whenever the row it sits in (e.g. the
        # DashboardHeroWidget status strip) is given less horizontal space
        # than its content needs -- silently compressing the badge instead
        # of guaranteeing it stays wide enough for its own label, which is
        # how a longer label ("THREAT: CRITICAL" vs. "THREAT: ELEVATED")
        # ends up visually colliding with whatever sits next to it.
        #
        # Minimum still lets the badge grow if the row has extra space,
        # but never lets it shrink below its own sizeHint, so the label is
        # always rendered in full -- any space pressure is resolved by the
        # row giving the badge its required minimum, not by compressing
        # badge content.
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
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