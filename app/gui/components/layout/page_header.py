"""
SOC-IQ Design System

Page Header

Reusable page header used across all
major application pages.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Spacing


class PageHeader(BaseWidget):
    """
    Standard page header.

    Displays:

    • Title
    • Subtitle
    • Status information
    • Last refresh time
    • Action buttons
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title_label = QLabel(title)
        self._subtitle_label = QLabel(subtitle)

        self._status_label = QLabel()
        self._refresh_label = QLabel()

        self._actions_layout = QHBoxLayout()

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title_label.setFont(fonts.display())
        self._title_label.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        self._subtitle_label.setFont(fonts.body())
        self._subtitle_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

        self._status_label.setFont(fonts.caption())
        self._status_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )
        self._status_label.hide()

        self._refresh_label.setFont(fonts.caption())
        self._refresh_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )
        self._refresh_label.hide()

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(Spacing.XS)

        title_layout.addWidget(self._title_label)

        if self._subtitle_label.text():
            title_layout.addWidget(self._subtitle_label)

        title_layout.addWidget(self._status_label)
        title_layout.addWidget(self._refresh_label)

        actions_container = QWidget()

        self._actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._actions_layout.setSpacing(Spacing.SM)
        self._actions_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        actions_container.setLayout(
            self._actions_layout
        )

        root = QHBoxLayout(self)

        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root.setSpacing(Spacing.LG)

        root.addLayout(title_layout)

        root.addStretch()

        root.addWidget(actions_container)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_title(
        self,
        title: str,
    ) -> None:
        """Update the page title."""
        self._title_label.setText(title)

    def set_subtitle(
        self,
        subtitle: str,
    ) -> None:
        """Update the page subtitle."""
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(
            bool(subtitle)
        )

    def set_status(
        self,
        label: str,
        value: str,
    ) -> None:
        """
        Update status text.

        Example:
            Database: Connected
        """

        self._status_label.setText(
            f"{label}: {value}"
        )
        self._status_label.show()

    def clear_status(self) -> None:
        """Hide the status label."""
        self._status_label.clear()
        self._status_label.hide()

    def set_last_refresh(
        self,
        timestamp: str,
    ) -> None:
        """
        Update the last refresh timestamp.
        """

        self._refresh_label.setText(
            f"Last Refresh: {timestamp}"
        )
        self._refresh_label.show()

    def clear_last_refresh(self) -> None:
        """Hide the refresh label."""
        self._refresh_label.clear()
        self._refresh_label.hide()

    def add_action(
        self,
        widget: QWidget,
    ) -> None:
        """Add an action widget."""
        self._actions_layout.addWidget(widget)

    def clear_actions(self) -> None:
        """Remove all action widgets."""

        while self._actions_layout.count():

            item = self._actions_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()