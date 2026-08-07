"""
SOC-IQ Dashboard Component

AI Security Co-Pilot Assistant Widget

Provides automated threat insights, automated pattern correlation, and recommended
analyst action triggers.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.feedback.status_badge import BadgeType, StatusBadge
from app.gui.design.tokens import Spacing


class AICopilotWidget(GlassCard):
    """
    AI Security Assistant card.
    """

    action_triggered = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # No analysis has actually run yet at construction time -- this
        # widget has no AI backend wired in here, so anything more
        # specific than "no analysis run" would be fabricated threat
        # intelligence. Real findings only ever reach the label via
        # set_insight(), called by whatever component performs (or
        # requests) real correlation/AI analysis.
        self._badge = StatusBadge("AI ASSISTANT IDLE", BadgeType.INFO)
        self._title = QLabel("SOC-IQ Threat Intelligence Co-Pilot")
        self._insight = QLabel(
            "No AI analysis has been run yet. Use \"Correlate Indicators\" "
            "or \"Generate Briefing\" to request one."
        )

        self._btn_correlate = AnimatedButton("Correlate Indicators")
        self._btn_briefing = AnimatedButton("Generate Briefing")

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Construct AI Assistant UI layout.
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
        main_layout.setSpacing(Spacing.MD)

        # Header Row
        header_row = QHBoxLayout()
        self._title.setFont(fonts.title())
        self._title.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 700; font-size: 16px;"
        )
        header_row.addWidget(self._title)
        header_row.addStretch()
        header_row.addWidget(self._badge)

        main_layout.addLayout(header_row)

        # Insight Text
        self._insight.setFont(fonts.body())
        self._insight.setStyleSheet(f"color: {palette.text_secondary};")
        self._insight.setWordWrap(True)
        main_layout.addWidget(self._insight)

        # Action Triggers Row
        action_row = QHBoxLayout()
        action_row.setSpacing(Spacing.MD)

        self._btn_correlate.clicked.connect(
            lambda: self.action_triggered.emit("Correlate Indicators")
        )
        self._btn_briefing.clicked.connect(
            lambda: self.action_triggered.emit("Generate Briefing")
        )

        action_row.addWidget(self._btn_correlate)
        action_row.addWidget(self._btn_briefing)
        action_row.addStretch()

        main_layout.addLayout(action_row)

        self.add_layout(main_layout)

    def set_insight(self, text: str) -> None:
        """
        Update AI insights text dynamically.
        """
        self._insight.setText(text)