"""
SOC-IQ Design System
Glass Card

A lighter surface built on top of ModernCard.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Radius


class GlassCard(ModernCard):
    """
    Glass-style reusable card.

    Uses the same API as ModernCard while
    providing a lighter visual appearance.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._apply_glass_theme()

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    def _apply_glass_theme(self) -> None:
        """Apply glass card styling."""

        palette = self.theme.palette

        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_secondary};
                border: 1px solid {palette.border_subtle};
                border-radius: {Radius.CARD}px;
            }}
            """
        )