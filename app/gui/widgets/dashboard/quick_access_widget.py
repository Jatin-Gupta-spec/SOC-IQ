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

        Compact horizontal action row. The top accent is the card
        frame's own border-top (see _apply_coherent_styling) rather
        than a separate inset bar widget, so there's no extra
        wrapper layout needed here.

        BATCH 03B: label truncation ("Analyze Report" / "Threat
        Intel Lookup" not fully fitting) was primarily a width-
        allocation problem at the dashboard_page.py level (this
        panel only had 1/3 of the top row's width against three
        real button labels -- fixed there, now 3/5 of the row).
        On top of that, each button is given an explicit
        (Minimum, Fixed) size policy here so Qt sizes it to its
        own text sizeHint rather than letting the QHBoxLayout
        compress it below that when space is tight -- a button
        that can't fit will now push its siblings or get clipped
        at the panel edge (visible, actionable) instead of silently
        truncating its own label (invisible, easy to miss in review).
        Margins/spacing are also trimmed slightly (MD/SM -> SM/XS)
        to give the buttons themselves more of the panel's width.
        """

        main_layout = QHBoxLayout()

        # SM/XS rather than MD/SM: every point of margin/spacing
        # trimmed here is a point handed back to the three button
        # labels, which is what was actually clipping.
        main_layout.setContentsMargins(
            Spacing.SM,
            Spacing.SM,
            Spacing.SM,
            Spacing.SM,
        )

        main_layout.setSpacing(
            Spacing.XS,
        )

        for button in (
            self._btn_analyze,
            self._btn_history,
            self._btn_intel,
        ):
            # Fixed horizontal policy: never shrink a button below
            # its label's natural width. If the panel is ever too
            # narrow for all three, the layout will clip/overflow
            # visibly at the edge rather than silently truncating
            # the label text inside a button that still looks "full
            # width".
            button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
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