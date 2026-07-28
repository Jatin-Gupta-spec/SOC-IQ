"""
SOC-IQ Design System
Loading Skeleton

Reusable loading placeholder component.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class LoadingSkeleton(BaseWidget):
    """
    Reusable loading placeholder.

    Displays configurable skeleton rows while
    content is being loaded.
    """

    def __init__(
        self,
        rows: int = 4,
        bar_height: int = 14,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._rows = rows
        self._bar_height = bar_height

        self._layout = QVBoxLayout(self)

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        self._layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._layout.setSpacing(Spacing.SM)

        for _ in range(self._rows):

            bar = QFrame()

            bar.setObjectName("skeletonBar")

            bar.setFixedHeight(self._bar_height)

            self._layout.addWidget(bar)

        self._layout.addStretch()

    def _apply_theme(self) -> None:
        palette = self.theme.palette

        self.setStyleSheet(
            f"""
            QFrame#skeletonBar {{
                background-color: {palette.surface_secondary};
                border-radius: {Radius.SM}px;
                border: none;
            }}
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def rows(self) -> int:
        """Return the current row count."""
        return self._rows

    def bar_height(self) -> int:
        """Return the current bar height."""
        return self._bar_height

    def set_rows(self, rows: int) -> None:
        """
        Rebuild the skeleton with a new
        number of rows.
        """

        self._rows = rows

        while self._layout.count():

            item = self._layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self._build_ui()

        self._apply_theme()

    def set_bar_height(self, height: int) -> None:
        """
        Update bar height.
        """

        self._bar_height = height

        self.set_rows(self._rows)