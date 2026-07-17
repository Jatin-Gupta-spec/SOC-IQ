"""
GUI application entry point for SOC-IQ.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.gui.styles.theme import get_stylesheet


def main() -> int:
    """
    Create and start the GUI application.
    """

    app = QApplication(sys.argv)

    app.setApplicationName("SOC-IQ")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SOC-IQ")

    app.setStyleSheet(get_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())