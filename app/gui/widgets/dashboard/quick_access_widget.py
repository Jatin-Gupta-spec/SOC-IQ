"""
SOC-IQ Dashboard

Quick Access Widget

Provides one-click action cards to encourage analyst
navigation into primary application modules.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from app.gui.components.buttons.animated_button import (
    AnimatedButton,
    ButtonVariant,
)
from app.gui.components.cards.modern_card import (
    ModernCard,
)
from app.gui.design.tokens import Radius, Spacing


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

        self._btn_analyze = AnimatedButton(
            "+ Analyze Report"
        )

        self._btn_history = AnimatedButton(
            "Browse History",
            variant=ButtonVariant.OUTLINE,
        )

        self._btn_intel = AnimatedButton(
            "Threat Intel Lookup",
            variant=ButtonVariant.OUTLINE,
        )

        super().__init__(parent)

        self._connect_signals()
        self._apply_coherent_styling()

        # No hard-coded height ceiling -- same reasoning as the
        # Hero strip: Maximum caps growth at the row's own natural
        # sizeHint (button height + margins) instead of a magic
        # pixel value that clips if button padding/font ever
        # changes.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

    def _apply_coherent_styling(self) -> None:
        """
        Give Quick Access the same brand-colored top accent as
        DashboardHeroWidget so the two read as one coherent
        command area (status + actions) instead of two unrelated
        cards sitting next to each other.

        Previously this styled a separate inset `_top_accent`
        widget sitting 16px inside the card's padded content area
        -- not flush with the card's actual edge, and inconsistent
        with Hero's border once Hero's own styling bug (targeting
        `self` instead of `self._frame`) is fixed. Now that Hero
        correctly overrides `self._frame`'s `border-top`, Quick
        Access does the same directly on its own `self._frame`
        instead of drawing a second, misaligned accent bar --
        giving both cards a matching, flush top edge with no
        redundant widget.
        """

        assert self._frame is not None

        palette = self.theme.palette

        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_primary};
                border: 1px solid {palette.border_default};
                border-top: 2px solid {palette.brand_primary};
                border-radius: {Radius.CARD}px;
            }}
            """
        )

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

        Compact horizontal action row -- replaces the previous
        full ModernCard (title + description + three vertically
        stacked full-width buttons), which cost far more vertical
        space than three navigation actions need. The top accent
        is now the card frame's own border-top (see
        _apply_coherent_styling) rather than a separate inset bar
        widget, so there's no extra wrapper layout needed here.
        """

        main_layout = QHBoxLayout()

        main_layout.setContentsMargins(
            Spacing.MD,
            Spacing.MD,
            Spacing.MD,
            Spacing.MD,
        )

        main_layout.setSpacing(
            Spacing.SM,
        )

        main_layout.addWidget(
            self._btn_analyze,
        )

        main_layout.addWidget(
            self._btn_history,
        )

        main_layout.addWidget(
            self._btn_intel,
        )

        main_layout.addStretch()

        self.add_layout(
            main_layout,
        )