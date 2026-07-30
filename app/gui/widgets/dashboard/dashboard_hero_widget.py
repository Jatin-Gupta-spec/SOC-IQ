"""
SOC-IQ Dashboard

Hero Banner Widget

Executive landing header displaying system operational readiness, active threat level, and analyst command center welcome.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
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
from app.gui.design.tokens import Spacing


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
        self.update_timestamp()

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

        palette = self.theme.palette
        fonts = self.theme.fonts

        self._greeting_label.setFont(fonts.title())
        self._greeting_label.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 700; font-size: 20px;"
        )

        self._sub_label.setFont(fonts.body())
        self._sub_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )
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

        badges_row = QHBoxLayout()
        badges_row.setSpacing(Spacing.SM)
        badges_row.addWidget(self._status_badge)
        badges_row.addWidget(self._threat_badge)

        self._timestamp_label.setFont(fonts.caption())
        self._timestamp_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )
        self._timestamp_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        right_box.addLayout(badges_row)
        right_box.addWidget(self._timestamp_label)

        container_layout.addLayout(right_box, 2)

        self.add_layout(container_layout)

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
