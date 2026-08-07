"""
SOC-IQ Dashboard

Quick Access Widget

Provides one-click action cards to encourage analyst
navigation into primary application modules.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import (
    AnimatedButton,
)
from app.gui.components.cards.modern_card import (
    ModernCard,
)
from app.gui.design.tokens import Spacing


class QuickAccessWidget(ModernCard):
    """
    Quick access navigation panel.
    """

    navigate_to_analyze = Signal()
    navigate_to_history = Signal()
    navigate_to_threat_intel = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        # ------------------------------------------
        # Create widgets BEFORE ModernCard.__init__()
        # ------------------------------------------

        self._title_label = QLabel(
            "Quick Access & Analyst Actions"
        )

        self._desc_label = QLabel(
            "Jump directly to operational modules."
        )

        self._desc_label.setWordWrap(True)

        self._btn_analyze = AnimatedButton(
            "+ Analyze Report"
        )

        self._btn_history = AnimatedButton(
            "Browse History"
        )

        self._btn_intel = AnimatedButton(
            "Threat Intel Lookup"
        )

        super().__init__(parent)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self._btn_analyze.button().clicked.connect(
            self.navigate_to_analyze.emit
        )

        self._btn_history.button().clicked.connect(
            self.navigate_to_history.emit
        )

        self._btn_intel.button().clicked.connect(
            self.navigate_to_threat_intel.emit
        )

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_contents(self) -> None:
        """
        Build widget layout.
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

        main_layout.setSpacing(
            Spacing.MD,
        )

        self._title_label.setFont(
            fonts.title()
        )

        self._title_label.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 600;
            """
        )

        self._desc_label.setFont(
            fonts.body()
        )

        self._desc_label.setStyleSheet(
            f"""
            color: {palette.text_secondary};
            """
        )

        main_layout.addWidget(
            self._title_label,
        )

        main_layout.addWidget(
            self._desc_label,
        )

        main_layout.addSpacing(Spacing.SM)

        buttons_layout = QVBoxLayout()

        buttons_layout.setSpacing(
            Spacing.SM,
        )

        buttons_layout.addWidget(
            self._btn_analyze,
        )

        buttons_layout.addWidget(
            self._btn_history,
        )

        buttons_layout.addWidget(
            self._btn_intel,
        )

        main_layout.addLayout(
            buttons_layout,
        )

        main_layout.addStretch()

        self.add_layout(
            main_layout,
        )