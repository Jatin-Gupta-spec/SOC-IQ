"""
IOC Distribution Widget

Displays IOC category distribution across all
investigations stored in SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Colors, Spacing


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

    # One distinct hue per IOC type, drawn from the existing
    # Colors.Chart palette (no new tokens introduced) so each bar
    # is visually distinguishable rather than all sharing the same
    # brand color.
    _TYPE_COLORS = (
        Colors.Chart.BLUE,
        Colors.Chart.CYAN,
        Colors.Chart.TEAL,
        Colors.Chart.GREEN,
        Colors.Chart.LIME,
        Colors.Chart.YELLOW,
        Colors.Chart.ORANGE,
        Colors.Chart.PURPLE,
    )

    def __init__(self) -> None:
        super().__init__()

        palette = self.theme.palette
        fonts = self.theme.fonts

        header_row = QHBoxLayout()

        title = QLabel("IOC Distribution")
        title.setFont(fonts.title())
        title.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 600;"
        )

        self._total_label = QLabel("0 total")
        self._total_label.setFont(fonts.caption())
        self._total_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._total_label)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(Spacing.SM)

        outer_layout = QVBoxLayout()
        outer_layout.addLayout(header_row)
        outer_layout.addLayout(self._rows_layout)

        self.add_layout(outer_layout)

        self._show_empty_state()

    def _clear_rows(self) -> None:
        while self._rows_layout.count():

            item = self._rows_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def _show_empty_state(self) -> None:
        self._clear_rows()

        palette = self.theme.palette
        fonts = self.theme.fonts

        label = QLabel("No IOC statistics available")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(fonts.body())
        label.setStyleSheet(
            f"color: {palette.text_secondary}; font-weight: 600;"
        )

        description = QLabel(
            "Indicators extracted from analyzed reports will be "
            "broken down here by type."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setFont(fonts.caption())
        description.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        self._rows_layout.addStretch()
        self._rows_layout.addWidget(label)
        self._rows_layout.addWidget(description)
        self._rows_layout.addStretch()

        self._total_label.setText("0 total")

    def load_distribution(
        self,
        distribution: dict[str, int],
    ) -> None:
        """
        Populate widget.
        """

        self._clear_rows()

        total = sum(distribution.values())

        if total == 0:
            self._show_empty_state()
            return

        self._total_label.setText(f"{total} total")

        palette = self.theme.palette
        fonts = self.theme.fonts

        # Preserve the preferred ordering for known types, but never
        # silently drop a type the backend returns that isn't in
        # IOC_ORDER yet — append anything unrecognized (alphabetized)
        # so the bars always account for the full total instead of
        # under-summing to less than 100%.
        ordered_types = [
            t for t in self.IOC_ORDER if t in distribution
        ] + sorted(
            t for t in distribution if t not in self.IOC_ORDER
        )

        for index, ioc_type in enumerate(ordered_types):

            value = distribution.get(
                ioc_type,
                0,
            )

            percent = int(
                (value / total) * 100
            )

            color = self._TYPE_COLORS[index % len(self._TYPE_COLORS)]

            title = QLabel(
                f"{ioc_type} ({value})"
            )
            title.setFont(fonts.caption())
            title.setStyleSheet(
                f"color: {palette.text_secondary};"
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

            progress.setFixedHeight(8)
            progress.setTextVisible(False)

            progress.setStyleSheet(
                f"""
                QProgressBar {{
                    background: {palette.surface_secondary};
                    border: none;
                    border-radius: 4px;
                }}

                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 4px;
                }}
                """
            )

            self._rows_layout.addWidget(title)
            self._rows_layout.addWidget(progress)