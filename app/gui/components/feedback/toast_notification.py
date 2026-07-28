"""
SOC-IQ Design System
Toast Notification

Reusable notification widget.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class ToastType(Enum):
    """Supported notification types."""

    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()


class ToastNotification(BaseWidget):
    """
    Reusable toast notification.

    Displays a message using semantic
    colours from the active theme.
    """

    def __init__(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._toast_type = toast_type

        self._label = QLabel(message)
        self._label.setWordWrap(True)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            Spacing.MD,
            Spacing.SM,
            Spacing.MD,
            Spacing.SM,
        )

        layout.setSpacing(Spacing.SM)

        layout.addWidget(self._label)

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._label.setFont(fonts.body())

        background, foreground = self._toast_colors()

        self.setStyleSheet(
            f"""
            ToastNotification {{
                background-color: {background};
                border-radius: {Radius.CARD}px;
            }}

            QLabel {{
                background: transparent;
                color: {foreground};
            }}
            """
        )

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _toast_colors(self) -> tuple[str, str]:
        palette = self.theme.palette

        mapping = {
            ToastType.INFO: (
                palette.info,
                palette.text_primary,
            ),
            ToastType.SUCCESS: (
                palette.success,
                palette.text_primary,
            ),
            ToastType.WARNING: (
                palette.warning,
                palette.text_primary,
            ),
            ToastType.ERROR: (
                palette.error,
                palette.text_primary,
            ),
        }

        return mapping[self._toast_type]

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def message(self) -> str:
        return self._label.text()

    def set_message(self, message: str) -> None:
        self._label.setText(message)

    def toast_type(self) -> ToastType:
        return self._toast_type

    def set_toast_type(
        self,
        toast_type: ToastType,
    ) -> None:
        self._toast_type = toast_type
        self._apply_theme()