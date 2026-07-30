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
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Spacing


@dataclass(slots=True)
class TimelineEvent:
    """
    Timeline event model.

    Backward compatible with previous versions while
    supporting richer enterprise event metadata.
    """

    timestamp: str
    title: str
    description: str = ""

    # Enterprise Event Feed additions
    severity: str = "INFO"
    source: str = ""
    icon: str = "●"


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

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self._theme = theme
        self._event = event

        self._build_ui()

    def _severity_color(self) -> str:
        """
        Returns the theme color for the event severity.
        """

        palette = self._theme.palette

        severity = self._event.severity.upper()

        if severity == "LOW":
            return palette.severity_low

        if severity == "MEDIUM":
            return palette.severity_medium

        if severity == "HIGH":
            return palette.severity_high

        if severity == "CRITICAL":
            return palette.severity_critical

        return palette.info

    def _build_ui(self) -> None:
        palette = self._theme.palette
        fonts = self._theme.fonts

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, Spacing.SM)

        card = QFrame()
        card.setMinimumHeight(130)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        card.setObjectName("timelineEventCard")

        card.setStyleSheet(
            f"""
            QFrame#timelineEventCard {{
                background-color:{palette.surface_primary};
                border:1px solid {palette.border_default};
                border-radius:12px;
            }}
            """
        )

        outer_layout = QHBoxLayout(card)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        accent = QFrame()
        accent.setFixedWidth(4)

        accent.setStyleSheet(
            f"""
            background:{self._severity_color()};
            border-top-left-radius:12px;
            border-bottom-left-radius:12px;
            """
        )

        outer_layout.addWidget(accent)

        content = QWidget()
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        outer_layout.addWidget(content)

        card_layout = QVBoxLayout(content)
        card_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        card_layout.setSpacing(Spacing.SM)

        header = QHBoxLayout()

        icon = QLabel(self._event.icon)
        icon.setFont(fonts.heading())

        title = QLabel(self._event.title)
        title.setWordWrap(True)
        title.setFont(fonts.heading())

        title.setStyleSheet(
            f"""
            color:{palette.text_primary};
            font-weight:600;
            """
        )

        severity = QLabel(self._event.severity.upper())
        severity.setMinimumWidth(70)
        severity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        severity.setFont(fonts.caption())

        severity_color = self._severity_color()

        severity.setStyleSheet(
            f"""
            background:{severity_color};
            color:white;
            border-radius:8px;
            padding:2px 8px;
            font-weight:600;
            """
        )

        header.addWidget(icon)
        header.addSpacing(Spacing.XS)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(severity)

        card_layout.addLayout(header)
        card_layout.addSpacing(Spacing.XS)

        if self._event.source:
            source = QLabel(self._event.source.upper())
            source.setFont(fonts.caption())

            source.setStyleSheet(
                f"""
                color:{palette.text_muted};
                letter-spacing:0.5px;
                """
            )
            card_layout.addWidget(source)

        if self._event.description:
            description = QLabel(self._event.description)
            description.setWordWrap(True)
            description.setFont(fonts.body())
            description.setStyleSheet(
                f"color:{palette.text_secondary};"
            )
            card_layout.addWidget(description)

        timestamp = QLabel(self._event.timestamp)
        timestamp.setFont(fonts.caption())
        timestamp.setAlignment(Qt.AlignmentFlag.AlignRight)
        timestamp.setStyleSheet(
            f"""
            color:{palette.text_muted};
            """
        )

        card_layout.addWidget(timestamp)

        root.addWidget(card)

        root.addStretch()


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
        self._container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
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

        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(self._container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(Spacing.MD)

        title = QLabel("Recent Security Activity")
        title.setFont(self.theme.fonts.title())
        title.setStyleSheet(
            f"color: {self.theme.palette.text_primary};"
        )

        root.addWidget(title)
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