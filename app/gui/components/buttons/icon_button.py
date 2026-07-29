"""
SOC-IQ Design System
Icon Button

Reusable icon-only button for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QWidget

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius


class IconButton(BaseWidget):
    """
    Reusable icon button.
    """

    def __init__(
        self,
        icon: QIcon,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._button = QPushButton(self)

        self._button.setIcon(icon)
        self._button.setIconSize(QSize(18, 18))
        self._button.setFixedSize(36, 36)

        if tooltip:
            self._button.setToolTip(tooltip)

        self._apply_theme()

    def _apply_theme(self) -> None:
        """
        Apply the current Design System theme.
        """
        palette = self.theme.palette

        self._button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette.surface_secondary};
                border: 1px solid {palette.border_default};
                border-radius: {Radius.BUTTON}px;
            }}

            QPushButton:hover {{
                background-color: {palette.surface_primary};
            }}

            QPushButton:pressed {{
                background-color: {palette.surface_elevated};
            }}

            QPushButton:disabled {{
                background-color: {palette.surface_secondary};
                color: {palette.text_disabled};
            }}
            """
        )

    @property
    def button(self) -> QPushButton:
        """Return the underlying QPushButton."""
        return self._button