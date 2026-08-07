"""
Professional circular risk gauge for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
)

from PySide6.QtWidgets import QWidget

from app.gui.design.theme.theme_manager import theme_manager


class RiskGaugeWidget(QWidget):
    """
    Circular risk score indicator.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self._score = 0

        self.setMinimumSize(
            170,
            170,
        )

    def set_score(
        self,
        score: int,
    ) -> None:

        self._score = max(
            0,
            min(
                score,
                100,
            ),
        )

        self.update()

    def paintEvent(
        self,
        event,
    ) -> None:

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
        )

        rect = self.rect().adjusted(
            15,
            15,
            -15,
            -15,
        )

        palette = theme_manager.palette

        pen = QPen()

        pen.setWidth(
            12,
        )

        pen.setColor(
            QColor(palette.border_subtle),
        )

        painter.setPen(
            pen,
        )

        painter.drawArc(
            rect,
            0,
            360 * 16,
        )

        if self._score >= 90:

            color = palette.severity_critical

        elif self._score >= 70:

            color = palette.severity_high

        elif self._score >= 40:

            color = palette.severity_medium

        else:

            color = palette.severity_low

        pen.setColor(
            QColor(color),
        )

        painter.setPen(
            pen,
        )

        span = int(
            -360
            * 16
            * self._score
            / 100
        )

        painter.drawArc(
            rect,
            90 * 16,
            span,
        )

        font = QFont()

        font.setPointSize(
            24,
        )

        font.setBold(
            True,
        )

        painter.setFont(
            font,
        )

        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            str(
                self._score,
            ),
        )