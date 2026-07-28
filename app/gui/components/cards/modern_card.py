"""
SOC-IQ Design System
Modern Card

Reusable card component for the SOC-IQ interface.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.theme.theme_manager import theme_manager
from app.gui.design.tokens import Radius, Spacing


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

        self._build_ui()
        self._create_layout()
        self._connect_signals()
        self._apply_theme()

    # --------------------------------------------------
    # UI Construction
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """Create internal widgets."""

        self._frame = QFrame(self)
        self._frame.setObjectName("modernCard")

    def _create_layout(self) -> None:
        """Create layouts."""

        self._content_layout = QVBoxLayout()

        self._content_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        self._content_layout.setSpacing(Spacing.MD)

        self._frame.setLayout(self._content_layout)

        self._root_layout = QVBoxLayout(self)

        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._root_layout.addWidget(self._frame)

    def _connect_signals(self) -> None:
        """Connect signals."""

        # Reserved for future interactions.
        return

    def _apply_theme(self) -> None:
        """Apply the active theme."""

        palette = theme_manager.palette

        self._frame.setStyleSheet(
            f"""
            QFrame#modernCard {{
                background-color: {palette.surface_primary};
                border: 1px solid {palette.border_default};
                border-radius: {Radius.CARD}px;
            }}
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def content_layout(self) -> QVBoxLayout:
        """
        Return the card's content layout.
        """

        assert self._content_layout is not None
        return self._content_layout

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the card."""

        self.content_layout().addWidget(widget)

    def add_layout(self, layout) -> None:
        """Add a child layout."""

        self.content_layout().addLayout(layout)

    def add_spacing(self, spacing: int) -> None:
        """Insert vertical spacing."""

        self.content_layout().addSpacing(spacing)

    def add_stretch(self) -> None:
        """Add stretch."""

        self.content_layout().addStretch()

    def clear(self) -> None:
        """
        Remove every child widget from the card.
        """

        layout = self.content_layout()

        while layout.count():

            item = layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def set_alignment(
        self,
        alignment: Qt.AlignmentFlag,
    ) -> None:
        """Set layout alignment."""

        self.content_layout().setAlignment(alignment)