"""
SOC-IQ Design System
Modern Card

Reusable card component for the SOC-IQ interface.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import (
    Radius,
    Spacing,
)


class ModernCard(BaseWidget):
    """
    Reusable modern card container.

    This component serves as the base surface for
    dashboard panels, metric cards, investigation
    summaries, threat intelligence panels and more.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._frame: QFrame | None = None
        self._content_layout: QVBoxLayout | None = None
        self._root_layout: QVBoxLayout | None = None

        # ------------------------------------------
        # Build the ModernCard itself first.
        # ------------------------------------------

        ModernCard._build_ui(self)

        self._create_layout()

        self._build_contents()

        # ------------------------------------------
        # Allow subclasses to populate the card.
        # ------------------------------------------

        self._connect_signals()

        ModernCard.refresh_theme(self)

    # --------------------------------------------------
    # Internal Card Construction
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Build the internal ModernCard widgets.

        Subclasses should NOT override this.
        Override _build_contents() instead.
        """

        self._frame = QFrame(self)
        self._frame.setObjectName(
            "modernCard"
        )

    def _create_layout(self) -> None:
        """
        Create layouts.
        """

        assert self._frame is not None

        self._content_layout = QVBoxLayout()

        self._content_layout.setContentsMargins(
            Spacing.CARD_PADDING,
            Spacing.CARD_PADDING,
            Spacing.CARD_PADDING,
            Spacing.CARD_PADDING,
        )

        self._content_layout.setSpacing(
            Spacing.CONTENT_GAP,
        )

        self._frame.setLayout(
            self._content_layout,
        )

        self._root_layout = QVBoxLayout(self)

        self._root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._root_layout.setSpacing(0)

        self._root_layout.addWidget(
            self._frame,
        )

    # --------------------------------------------------
    # Subclass Hook
    # --------------------------------------------------

    def _build_contents(self) -> None:
        """
        Override this in subclasses.

        Called from ModernCard's own __init__, before the
        subclass's __init__ body has finished running. If your
        subclass needs instance state (models, services, etc.)
        available inside this method, set those attributes on
        `self` BEFORE calling `super().__init__()` in your
        subclass constructor — see InvestigationQueueWidget for
        an example of this pattern. This is a deliberate
        template-method design, not an oversight; don't reorder
        the base class's init sequence to "fix" it without
        checking every subclass that depends on the current order.
        """

        return

    # --------------------------------------------------
    # Signals
    # --------------------------------------------------

    def _connect_signals(self) -> None:
        """
        Connect signals.

        Reserved for future use.
        """

        return

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    def _apply_theme(self) -> None:
        """
        Apply active theme.

        Flat surface, thin border, subtle top accent, and a
        border-color hover state so interactive cards read
        differently from static ones without needing a new
        widget subclass.
        """

        assert self._frame is not None

        palette = self.palette

        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_primary};
                border: 1px solid {palette.border_default};
                border-top: 2px solid {palette.border_default};
                border-radius: {Radius.CARD}px;
            }}

            QFrame#modernCard:hover {{
                border: 1px solid {palette.border_strong};
                border-top: 2px solid {palette.brand_primary};
            }}
            """
        )

    def _apply_elevation(self) -> None:
        """
        Reserved for future elevation implementation.

        Intentionally left empty to avoid rendering issues with
        Qt item views (QTableView/QTableWidget).
        """
        return

    def refresh_theme(self) -> None:
        """
        Refresh the card theme and elevation.
        """

        self._apply_theme()
        self._apply_elevation()

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def content_layout(
        self,
    ) -> QVBoxLayout:

        assert self._content_layout is not None
        return self._content_layout

    def add_widget(
        self,
        widget: QWidget,
    ) -> None:

        self.content_layout().addWidget(
            widget,
        )

    def add_layout(
        self,
        layout: QLayout,
    ) -> None:

        self.content_layout().addLayout(
            layout,
        )

    def add_spacing(
        self,
        spacing: int,
    ) -> None:

        self.content_layout().addSpacing(
            spacing,
        )

    def add_stretch(
        self,
    ) -> None:

        self.content_layout().addStretch()

    def _clear_layout(
        self,
        layout: QLayout,
    ) -> None:
        """
        Recursively remove all items from a layout.

        This clears child widgets, nested layouts, and spacer
        items to ensure the layout is completely reset.
        """

        while layout.count():

            item = layout.takeAt(0)

            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()

            elif child_layout is not None:
                self._clear_layout(child_layout)


    def clear(
        self,
    ) -> None:
        """
        Remove all content from the card.
        """

        self._clear_layout(
            self.content_layout()
        )

    def set_alignment(
        self,
        alignment: Qt.AlignmentFlag,
    ) -> None:

        self.content_layout().setAlignment(
            alignment,
        )