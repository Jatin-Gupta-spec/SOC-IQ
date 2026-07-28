"""
SOC-IQ Design System
Panel

Reusable layout container.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class Panel(BaseWidget):
    """
    Reusable panel container.

    Provides a lightweight themed container
    for grouping related widgets.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._layout = QVBoxLayout(self)

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        self._layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        self._layout.setSpacing(Spacing.MD)

    def _apply_theme(self) -> None:
        palette = self.theme.palette

        self.setStyleSheet(
            f"""
            Panel {{
                background-color: {palette.background_secondary};
                border: 1px solid {palette.border_default};
                border-radius: {Radius.PANEL}px;
            }}
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def add_spacing(self, spacing: int) -> None:
        self._layout.addSpacing(spacing)

    def add_stretch(self) -> None:
        self._layout.addStretch()

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()