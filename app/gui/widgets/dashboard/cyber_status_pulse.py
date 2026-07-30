"""
SOC-IQ Dashboard Component

Cyber Status Pulse Widget

Renders a live pulsing status ring with a breathing radial glow to visually communicate
active real-time monitoring state.
"""

from __future__ import annotations

import math
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget


class CyberStatusPulse(QWidget):
    """
    Live pulsing status indicator with radial glow animation.
    """

    def __init__(
        self,
        color: QColor | str = "#10B981",
        size: int = 18,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if isinstance(color, str):
            self._color = QColor(color)
        else:
            self._color = color

        self._dot_size = size
        self._pulse_step = 0.0

        self.setFixedSize(self._dot_size * 2, self._dot_size * 2)

        # Pulse timer running at ~30 FPS for smooth breathing animation
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_pulse_tick)
        self._timer.start()

    def set_color(self, color: QColor | str) -> None:
        """
        Update status color.
        """
        if isinstance(color, str):
            self._color = QColor(color)
        else:
            self._color = color
        self.update()

    def _on_pulse_tick(self) -> None:
        """
        Advance pulse animation cycle.
        """
        self._pulse_step += 0.08
        if self._pulse_step >= 2 * math.pi:
            self._pulse_step = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        """
        Custom paint radial glow pulse.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0

        # Calculate breathing radius factor between 0.7 and 1.2
        glow_factor = 0.7 + 0.3 * (1.0 + math.sin(self._pulse_step)) / 2.0
        glow_radius = (self._dot_size / 1.1) * glow_factor

        # Outer radial glow
        radial_grad = QRadialGradient(center_x, center_y, glow_radius)
        glow_color = QColor(self._color)
        glow_color.setAlphaF(0.35 * (1.0 - (glow_factor - 0.7) / 0.6))
        radial_grad.setColorAt(0.0, glow_color)

        transparent_color = QColor(self._color)
        transparent_color.setAlpha(0)
        radial_grad.setColorAt(1.0, transparent_color)

        painter.setBrush(radial_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            center_x - glow_radius,
            center_y - glow_radius,
            glow_radius * 2,
            glow_radius * 2,
        )

        # Core solid dot
        core_radius = self._dot_size / 3.2
        painter.setBrush(self._color)
        painter.drawEllipse(
            center_x - core_radius,
            center_y - core_radius,
            core_radius * 2,
            core_radius * 2,
        )
