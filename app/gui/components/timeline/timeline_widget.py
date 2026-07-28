"""
SOC-IQ Design System
Timeline Widget

Reusable timeline component for displaying
chronological events.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Spacing


@dataclass(slots=True)
class TimelineEvent:
    """
    Timeline event model.
    """

    timestamp: str
    title: str
    description: str = ""


class _TimelineEventWidget(QWidget):
    """
    Internal widget representing one event.
    """

    def __init__(
        self,
        event: TimelineEvent,
        theme,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._theme = theme
        self._event = event

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, Spacing.MD)
        layout.setSpacing(Spacing.XS)

        palette = self._theme.palette
        fonts = self._theme.fonts

        timestamp = QLabel(self._event.timestamp)
        timestamp.setFont(fonts.caption())
        timestamp.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

        title = QLabel(self._event.title)
        title.setFont(fonts.heading())
        title.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        layout.addWidget(timestamp)
        layout.addWidget(title)

        if self._event.description:
            description = QLabel(self._event.description)
            description.setWordWrap(True)
            description.setFont(fonts.body())
            description.setStyleSheet(
                f"color: {palette.text_secondary};"
            )

            layout.addWidget(description)


class TimelineWidget(BaseWidget):
    """
    Reusable vertical timeline.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._scroll = QScrollArea()
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        self._layout.setContentsMargins(
            Spacing.MD,
            Spacing.MD,
            Spacing.MD,
            Spacing.MD,
        )

        self._layout.setSpacing(Spacing.LG)
        self._layout.addStretch()

        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(self._container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def add_event(
        self,
        event: TimelineEvent,
    ) -> None:
        widget = _TimelineEventWidget(
            event,
            self.theme,
        )

        self._layout.insertWidget(
            self._layout.count() - 1,
            widget,
        )

    def clear(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()