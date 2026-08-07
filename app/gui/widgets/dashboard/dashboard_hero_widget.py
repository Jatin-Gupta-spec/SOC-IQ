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
    QVBoxLayout,
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
            "SOC-IQ Analyst Command Center"
        )

        self._sub_label = QLabel(
            "Real-time operational intelligence, threat monitoring, and automated forensic analysis."
        )

        # Small live-status pulse dot shown next to the
        # operational badge — gives the hero a "this is a
        # live system" feel instead of a static label.
        self._pulse_dot = QLabel()

        self._status_badge = StatusBadge(
            "SYSTEM OPERATIONAL",
            BadgeType.SUCCESS,
        )

        self._threat_badge = StatusBadge(
            "THREAT LEVEL: ELEVATED",
            BadgeType.WARNING,
        )

        self._timestamp_label = QLabel()

        self._build_hero_ui()
        self.refresh_theme()
        self.update_timestamp()

        # Keep the "System Time" readout genuinely live instead
        # of only updating on investigation events — matches the
        # "real-time" language in the subtitle and the pulse dot.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self.update_timestamp)
        self._clock_timer.start()

    def _build_hero_ui(self) -> None:
        """
        Construct the hero banner layout.
        """

        container_layout = QHBoxLayout()

        container_layout.setContentsMargins(
            Spacing.LG,
            Spacing.MD,
            Spacing.LG,
            Spacing.MD,
        )

        container_layout.setSpacing(Spacing.LG)

        # Left side: Greeting & Subtitle
        left_box = QVBoxLayout()
        left_box.setSpacing(Spacing.XS)

        self._sub_label.setWordWrap(True)

        left_box.addWidget(self._greeting_label)
        left_box.addWidget(self._sub_label)

        container_layout.addLayout(left_box, 3)

        # Right side: Status Badges & Timestamp
        right_box = QVBoxLayout()
        right_box.setSpacing(Spacing.SM)
        right_box.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._pulse_dot.setFixedSize(8, 8)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(Spacing.SM)
        badges_row.addWidget(
            self._pulse_dot,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        badges_row.addWidget(self._status_badge)
        badges_row.addWidget(self._threat_badge)

        self._timestamp_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        right_box.addLayout(badges_row)
        right_box.addWidget(self._timestamp_label)

        container_layout.addLayout(right_box, 2)

        self.add_layout(container_layout)

        # Flatten the inherited glass treatment in favor of a
        # solid elevated surface with a brand-colored top
        # accent — matches the flat-surface / no-glassmorphism
        # direction used for ModernCard elsewhere in the app.

    def refresh_theme(self) -> None:
        """
        Refresh hero styling.
        """

        palette = self.palette
        fonts = self.fonts

        self._greeting_label.setFont(fonts.display())
        self._greeting_label.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 700;
            """
        )

        self._sub_label.setFont(fonts.body())
        self._sub_label.setStyleSheet(
            f"color: {palette.text_secondary};"
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

        self.setStyleSheet(
            f"""
            DashboardHeroWidget {{
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
        """
        now = datetime.now().strftime("%d %b %Y | %H:%M:%S")
        self._timestamp_label.setText(f"System Time: {now}")

    def set_threat_level(self, level: str, badge_type: BadgeType) -> None:
        """
        Update the threat level indicator.
        """
        self._threat_badge.set_text(f"THREAT LEVEL: {level.upper()}")
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