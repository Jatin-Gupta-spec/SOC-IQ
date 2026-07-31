"""
IOC Distribution Widget

Displays IOC category distribution across all
investigations stored in SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from app.gui.components.cards.modern_card import ModernCard


class IOCDistributionWidget(ModernCard):
    """
    Displays IOC distribution statistics.
    """

    IOC_ORDER = (
        "IPv4",
        "Domain",
        "URL",
        "Email",
        "MD5",
        "SHA1",
        "SHA256",
        "CVE",
    )

    def __init__(self) -> None:
        super().__init__()

        self._layout = QVBoxLayout()
        self._layout.setSpacing(10)

        self.add_layout(self._layout)

    def load_distribution(
        self,
        distribution: dict[str, int],
    ) -> None:
        """
        Populate widget.
        """

        while self._layout.count():

            item = self._layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        total = sum(distribution.values())

        if total == 0:

            label = QLabel(
                "No IOC statistics available."
            )

            self._layout.addWidget(label)
            return

        for ioc_type in self.IOC_ORDER:

            value = distribution.get(
                ioc_type,
                0,
            )

            percent = int(
                (value / total) * 100
            )

            title = QLabel(
                f"{ioc_type} ({value})"
            )

            progress = QProgressBar()

            progress.setRange(
                0,
                100,
            )

            progress.setValue(percent)

            progress.setFormat(
                f"{percent}%"
            )

            self._layout.addWidget(title)
            self._layout.addWidget(progress)