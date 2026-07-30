"""
SOC-IQ Dashboard Component

Cyber Hero Banner Widget

High-impact Cyber Operations Hero Header featuring live status pulsing indicator ring,
active threat posture telemetry, and system time ticker.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.feedback.status_badge import BadgeType, StatusBadge
from app.gui.design.tokens import Spacing
from app.gui.widgets.dashboard.cyber_status_pulse import CyberStatusPulse


class CyberHeroBanner(GlassCard):
    """
    Next-Gen Cyber Operations Hero Header Banner.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._pulse = CyberStatusPulse(color="#10B981", size=18)
        self._title = QLabel(
            "SOC-IQ"
        )

        self._subtitle = QLabel(
            "Cyber Operations Workbench"
        )

        self._posture_badge = StatusBadge(
            "",
            BadgeType.DEFAULT,
        )

        self.set_posture(
            "Loading",
            BadgeType.INFO,
        )
        self._engine_badge = StatusBadge(
            "",
            BadgeType.DEFAULT,
        )

        self.set_engine_status(
            "Initializing",
            BadgeType.INFO,
        )

    def set_engine_status(
        self,
        text: str,
        badge_type: BadgeType,
    ) -> None:

        self._engine_badge.set_text(
            f"ENGINE: {text.upper()}"
        )

        self._engine_badge.set_badge_type(
            badge_type,
        )

        self._clock_label = QLabel()

        self._analysis_label = QLabel(
            "Last Analysis: None"
        )

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_clock)
        self._timer.start(1000)

        self.update_clock()

    def _build_ui(self) -> None:
        """
        Construct Hero Banner layout.
        """
        palette = self.theme.palette
        fonts = self.theme.fonts

        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(
            Spacing.LG,
            Spacing.MD,
            Spacing.LG,
            Spacing.MD,
        )
        container_layout.setSpacing(Spacing.LG)

        # Left Column: Pulse & Title
        left_box = QHBoxLayout()
        left_box.setSpacing(Spacing.MD)
        left_box.addWidget(self._pulse, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(Spacing.XS)

        self._title.setFont(fonts.title())
        self._title.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 800; font-size: 20px; letter-spacing: 1px;"
        )

        self._subtitle.setFont(fonts.body())
        self._subtitle.setStyleSheet(f"color: {palette.text_secondary};")

        text_box.addWidget(self._title)
        text_box.addWidget(self._subtitle)

        left_box.addLayout(text_box)
        container_layout.addLayout(left_box, 3)

        # Right Column: Badges & Clock
        right_box = QVBoxLayout()
        right_box.setSpacing(Spacing.SM)
        right_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(Spacing.SM)
        badge_row.addWidget(self._posture_badge)
        badge_row.addWidget(self._engine_badge)

        self._clock_label.setFont(fonts.caption())
        self._clock_label.setStyleSheet(f"color: {palette.text_muted}; font-weight: 600;")
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._analysis_label.setFont(
            fonts.caption(),
        )

        self._analysis_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

        self._analysis_label.setAlignment(
            Qt.AlignmentFlag.AlignRight,
        )

        right_box.addLayout(badge_row)
        right_box.addWidget(self._clock_label)

        container_layout.addLayout(right_box, 2)

        self.add_layout(container_layout)

    def update_clock(self) -> None:
        """
        Update dynamic time string.
        """
        now = datetime.now().strftime("%d %b %Y | %H:%M:%S")
        self._clock_label.setText(f"System Telemetry Time: {now}")

    def set_posture(
        self,
        text: str,
        badge_type: BadgeType,
    ) -> None:

        self._posture_badge.set_text(
            f"POSTURE: {text.upper()}"
        )

        self._posture_badge.set_badge_type(
            badge_type,
        )

        palette = self.theme.palette

        colors = {
            BadgeType.SUCCESS: palette.success,
            BadgeType.WARNING: palette.warning,
            BadgeType.ERROR: palette.error,
            BadgeType.INFO: palette.info,
        }

        self._pulse.set_color(
            colors.get(
                badge_type,
                palette.info,
            )
        )
