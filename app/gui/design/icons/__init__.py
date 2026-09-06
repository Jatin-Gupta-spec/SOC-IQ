"""
SOC-IQ Design System
Icon Tokens

Centralized, vector-drawn icon set for the SOC-IQ desktop
application.

Icons are rendered with QPainter at request time rather than
shipped as unicode/emoji characters or bitmap assets. This keeps
icons crisp at any DPI, themeable (color is a parameter, so icons
always match the current design tokens), and dependency-free.

Usage:
    from app.gui.design.icons import Icon, icon_pixmap, icon

    label.setPixmap(icon_pixmap(Icon.DATABASE, color=Colors.Text.PRIMARY, size=18))
    button.setIcon(icon(Icon.CLOSE, color=Colors.Text.MUTED))

Do not use emoji or unicode glyphs as UI icons anywhere in the
application. Reference Icon.* instead.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


class Icon(str, Enum):
    """Enumerates the icons available in the SOC-IQ icon set."""

    REPORT = "report"
    INDICATOR = "indicator"
    ALERT = "alert"
    DATABASE = "database"
    FOLDER = "folder"
    CLOCK = "clock"
    CHECK = "check"
    CLOSE = "close"
    SEARCH = "search"
    SHIELD = "shield"


def _draw(painter: QPainter, name: Icon, rect: QRectF) -> None:
    """Draws the requested icon glyph inside ``rect``."""

    w, h = rect.width(), rect.height()
    cx, cy = rect.center().x(), rect.center().y()

    if name == Icon.REPORT:
        body = rect.adjusted(w * 0.2, h * 0.1, -w * 0.2, -h * 0.1)
        painter.drawRoundedRect(body, w * 0.06, w * 0.06)
        for i in range(3):
            y = body.top() + body.height() * (0.28 + i * 0.26)
            painter.drawLine(
                QPointF(body.left() + w * 0.12, y),
                QPointF(body.right() - w * 0.12, y),
            )

    elif name == Icon.INDICATOR:
        radius = min(w, h) * 0.28
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

    elif name == Icon.ALERT:
        path = QPainterPath()
        path.moveTo(cx, rect.top() + h * 0.08)
        path.lineTo(rect.right() - w * 0.1, rect.bottom() - h * 0.12)
        path.lineTo(rect.left() + w * 0.1, rect.bottom() - h * 0.12)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(
            QPointF(cx, rect.top() + h * 0.38),
            QPointF(cx, rect.top() + h * 0.66),
        )
        painter.drawPoint(QPointF(cx, rect.bottom() - h * 0.24))

    elif name == Icon.DATABASE:
        top = rect.adjusted(w * 0.14, h * 0.08, -w * 0.14, -h * 0.68)
        painter.drawEllipse(top)
        painter.drawLine(
            QPointF(rect.left() + w * 0.14, top.center().y()),
            QPointF(rect.left() + w * 0.14, rect.bottom() - h * 0.12),
        )
        painter.drawLine(
            QPointF(rect.right() - w * 0.14, top.center().y()),
            QPointF(rect.right() - w * 0.14, rect.bottom() - h * 0.12),
        )
        path = QPainterPath()
        path.moveTo(rect.left() + w * 0.14, rect.bottom() - h * 0.12)
        path.arcTo(
            QRectF(
                rect.left() + w * 0.14,
                rect.bottom() - h * 0.32,
                w * 0.72,
                h * 0.24,
            ),
            180,
            180,
        )
        painter.drawPath(path)

    elif name == Icon.FOLDER:
        path = QPainterPath()
        path.moveTo(rect.left() + w * 0.1, rect.bottom() - h * 0.15)
        path.lineTo(rect.left() + w * 0.1, rect.top() + h * 0.3)
        path.lineTo(rect.left() + w * 0.4, rect.top() + h * 0.3)
        path.lineTo(rect.left() + w * 0.5, rect.top() + h * 0.15)
        path.lineTo(rect.right() - w * 0.1, rect.top() + h * 0.15)
        path.lineTo(rect.right() - w * 0.1, rect.bottom() - h * 0.15)
        path.closeSubpath()
        painter.drawPath(path)

    elif name == Icon.CLOCK:
        painter.drawEllipse(rect.adjusted(w * 0.08, h * 0.08, -w * 0.08, -h * 0.08))
        painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - h * 0.26))
        painter.drawLine(QPointF(cx, cy), QPointF(cx + w * 0.18, cy))

    elif name == Icon.CHECK:
        path = QPainterPath()
        path.moveTo(rect.left() + w * 0.16, cy)
        path.lineTo(cx - w * 0.06, rect.bottom() - h * 0.2)
        path.lineTo(rect.right() - w * 0.14, rect.top() + h * 0.22)
        painter.drawPath(path)

    elif name == Icon.CLOSE:
        painter.drawLine(
            QPointF(rect.left() + w * 0.2, rect.top() + h * 0.2),
            QPointF(rect.right() - w * 0.2, rect.bottom() - h * 0.2),
        )
        painter.drawLine(
            QPointF(rect.right() - w * 0.2, rect.top() + h * 0.2),
            QPointF(rect.left() + w * 0.2, rect.bottom() - h * 0.2),
        )

    elif name == Icon.SEARCH:
        lens = rect.adjusted(w * 0.12, h * 0.12, -w * 0.34, -h * 0.34)
        painter.drawEllipse(lens)
        painter.drawLine(
            QPointF(lens.right() - w * 0.02, lens.bottom() - h * 0.02),
            QPointF(rect.right() - w * 0.12, rect.bottom() - h * 0.12),
        )

    elif name == Icon.SHIELD:
        path = QPainterPath()
        path.moveTo(cx, rect.top() + h * 0.08)
        path.lineTo(rect.right() - w * 0.14, rect.top() + h * 0.22)
        path.lineTo(rect.right() - w * 0.14, rect.top() + h * 0.55)
        path.cubicTo(
            rect.right() - w * 0.14,
            rect.bottom() - h * 0.1,
            cx,
            rect.bottom() - h * 0.02,
            cx,
            rect.bottom() - h * 0.02,
        )
        path.cubicTo(
            cx,
            rect.bottom() - h * 0.02,
            rect.left() + w * 0.14,
            rect.bottom() - h * 0.1,
            rect.left() + w * 0.14,
            rect.top() + h * 0.55,
        )
        path.lineTo(rect.left() + w * 0.14, rect.top() + h * 0.22)
        path.closeSubpath()
        painter.drawPath(path)


def icon_pixmap(
    name: Icon,
    color: str,
    size: int = 18,
    stroke_width: float = 1.6,
) -> QPixmap:
    """
    Renders an icon token to a themeable QPixmap.

    ``color`` should always come from the design-token palette
    (e.g. ``Colors.Text.PRIMARY``, ``Colors.Severity.CRITICAL``)
    rather than being hardcoded by callers.
    """

    device_pixmap = QPixmap(size, size)
    device_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(device_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(stroke_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    if name == Icon.INDICATOR:
        painter.setBrush(QColor(color))
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)

    rect = QRectF(0, 0, size, size)
    _draw(painter, name, rect)

    painter.end()
    return device_pixmap


def icon(name: Icon, color: str, size: int = 18) -> QIcon:
    """Renders an icon token to a themeable QIcon."""

    return QIcon(icon_pixmap(name, color=color, size=size))
