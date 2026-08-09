"""
SOC-IQ Dashboard

Hero Banner Widget

Executive landing header displaying system operational readiness, active threat level, and analyst command center welcome.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.feedback.status_badge import (
    BadgeType,
    StatusBadge,
)
from app.gui.design.tokens import Radius, Spacing


class DashboardHeroWidget(GlassCard):
    """
    Hero banner for the SOC-IQ landing dashboard.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._greeting_label = QLabel(
            "SOC-IQ"
        )

        # Small live-status pulse dot shown next to the
        # operational badge — gives the hero a "this is a
        # live system" feel instead of a static label.
        self._pulse_dot = QLabel()

        self._status_badge = StatusBadge(
            "OPERATIONAL",
            BadgeType.SUCCESS,
        )

        self._threat_badge = StatusBadge(
            "THREAT: ELEVATED",
            BadgeType.WARNING,
        )

        self._timestamp_label = QLabel()

        self._build_hero_ui()
        self.refresh_theme()
        self.update_timestamp()

        # No hard-coded height ceiling. Instead, the strip's height
        # is left to its own natural sizeHint (driven by the label
        # font, badge heights, and the layout margins below), and
        # the vertical size policy caps growth at that natural size
        # -- Maximum means "never grow past sizeHint" without
        # pinning to a magic pixel number that clips real content
        # if a badge's font or padding ever changes.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        # Keep the "System Time" readout genuinely live instead
        # of only updating on investigation events — reinforces
        # the same "this is a live system" signal as the pulse dot.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self.update_timestamp)
        self._clock_timer.start()

    def _build_hero_ui(self) -> None:
        """
        Construct the hero banner layout.

        Single compact horizontal status strip (target ~48-56px)
        instead of the previous two-column layout built around a
        large display greeting and a long descriptive subtitle:

            [SOC-IQ]  ...  [pulse] [operational] [threat] [time]
        """

        container_layout = QHBoxLayout()

        container_layout.setContentsMargins(
            Spacing.LG,
            Spacing.MD,
            Spacing.LG,
            Spacing.MD,
        )

        container_layout.setSpacing(Spacing.SM)

        container_layout.addWidget(self._greeting_label)

        container_layout.addStretch()

        self._pulse_dot.setFixedSize(8, 8)

        container_layout.addWidget(
            self._pulse_dot,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        container_layout.addWidget(self._status_badge)
        container_layout.addWidget(self._threat_badge)
        container_layout.addWidget(self._timestamp_label)

        self.add_layout(container_layout)

        # Flatten the inherited glass treatment in favor of a
        # solid elevated surface with a brand-colored top
        # accent — matches the flat-surface / no-glassmorphism
        # direction used for ModernCard elsewhere in the app.

    def refresh_theme(self) -> None:
        """
        Refresh hero styling.

        Root-cause fix: this used to call `self.setStyleSheet(...)`,
        styling the outer DashboardHeroWidget/GlassCard/ModernCard
        instance. ModernCard's actual paint surface is `self._frame`
        (a QFrame added with zero margins, filling the entire
        widget) -- styling `self` instead of `self._frame` had no
        visible effect, because the frame sits on top and occludes
        it. `self._frame` was left showing whatever GlassCard's own
        `refresh_theme()` (never called, since this override didn't
        chain to `super()`) or ModernCard's base `_apply_theme()`
        (always applied once at construction via the explicit
        `ModernCard.refresh_theme(self)` call in `ModernCard.__init__`)
        had set it to -- i.e. the plain flat-card look, not the
        intended elevated surface + brand-colored top accent.

        Fixed the same way GlassCard.refresh_theme() does it:
        target `self._frame` directly with a `QFrame#modernCard`
        selector.
        """

        palette = self.palette
        fonts = self.fonts

        self._greeting_label.setFont(fonts.title())
        self._greeting_label.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 700;
            """
        )

        self._timestamp_label.setFont(fonts.caption())
        self._timestamp_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        self._pulse_dot.setStyleSheet(
            f"""
            background-color: {palette.success};
            border-radius: 4px;
            """
        )

        assert self._frame is not None

        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_elevated};
                border: 1px solid {palette.border_default};
                border-top: 2px solid {palette.brand_primary};
                border-radius: {Radius.CARD}px;
            }}
            """
        )

    def update_timestamp(self) -> None:
        """
        Update the timestamp text.

        Shows time only (no date, no "System Time:" prefix) -- in
        the compact hero strip, sitting directly next to the live
        pulse dot and status badges, the shorter live-clock reading
        is unambiguous and saves the horizontal room the fuller
        format was costing at the minimum supported window width.
        """
        now = datetime.now().strftime("%H:%M:%S")
        self._timestamp_label.setText(f"Time: {now}")

    def set_threat_level(self, level: str, badge_type: BadgeType) -> None:
        """
        Update the threat level indicator.
        """
        self._threat_badge.set_text(f"THREAT: {level.upper()}")
        self._threat_badge.set_badge_type(badge_type)

        # Keep the pulse dot color aligned with severity so the
        # whole hero reads as one coherent status signal rather
        # than a static badge plus an unrelated green dot.
        palette = self.palette

        color_map = {
            BadgeType.SUCCESS: palette.success,
            BadgeType.WARNING: palette.warning,
            BadgeType.ERROR: palette.error,
            BadgeType.INFO: palette.info,
        }

        dot_color = color_map.get(badge_type, palette.success)

        self._pulse_dot.setStyleSheet(
            f"""
            background-color: {dot_color};
            border-radius: 4px;
            """
        )