"""
IOC Distribution Widget

Displays IOC category distribution across all
investigations stored in SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
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

        # Replaces the previous per-type stacked label+progress-bar
        # rows (which could run past 300px for 8 IOC types) with a
        # single segmented horizontal bar plus a compact multi-column
        # legend, rebuilt fresh into this layout on every
        # load_distribution() call.
        self._display_layout = QVBoxLayout()
        self._display_layout.setSpacing(Spacing.MD)

        outer_layout = QVBoxLayout()
        outer_layout.addLayout(header_row)
        outer_layout.addLayout(self._display_layout)

        self.add_layout(outer_layout)

        self._show_empty_state()

    def _clear_display(self) -> None:
        while self._display_layout.count():

            item = self._display_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def _show_empty_state(self) -> None:
        self._clear_display()

        palette = self.theme.palette
        fonts = self.theme.fonts

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

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

        container_layout.addWidget(label)
        container_layout.addWidget(description)

        self._display_layout.addWidget(container)

        self._total_label.setText("0 total")

    def load_distribution(
        self,
        distribution: dict[str, int],
    ) -> None:
        """
        Populate widget.

        Contract unchanged: takes the same {ioc_type: count} dict as
        before, preserves IOC_ORDER/_TYPE_COLORS, still accounts for
        every type present (known or unrecognized), and still shows
        the empty state when total == 0. Only the presentation
        changed, from stacked label+progress-bar rows to one
        segmented bar plus a compact legend.
        """

        self._clear_display()

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
        # so the bar/legend always account for the full total instead
        # of under-summing to less than 100%.
        ordered_types = [
            t for t in self.IOC_ORDER if t in distribution
        ] + sorted(
            t for t in distribution if t not in self.IOC_ORDER
        )

        # --------------------------------------------------
        # Segmented bar
        # --------------------------------------------------

        bar_container = QWidget()
        bar_container.setFixedHeight(Spacing.LG)

        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(3)

        # --------------------------------------------------
        # Compact legend (2-4 columns depending on item count)
        # --------------------------------------------------

        legend_container = QWidget()

        legend_layout = QGridLayout(legend_container)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setHorizontalSpacing(Spacing.MD)
        legend_layout.setVerticalSpacing(Spacing.XS)

        columns = min(4, max(len(ordered_types), 1))

        for index, ioc_type in enumerate(ordered_types):

            value = distribution.get(
                ioc_type,
                0,
            )

            color = self._TYPE_COLORS[index % len(self._TYPE_COLORS)]

            # Segment width proportional to this type's share of the
            # total. A zero-count type (still present in the
            # distribution dict) simply gets zero stretch -- it stays
            # in the legend but contributes no visible bar width.
            segment = QWidget()
            segment.setStyleSheet(
                f"background-color: {color}; border-radius: 2px;"
            )
            bar_layout.addWidget(segment, max(value, 0))

            swatch = QLabel()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(
                f"background-color: {color}; border-radius: 2px;"
            )

            # Type name and count are two labels rather than one
            # formatted string so the type name can carry slightly
            # more visual weight than its count, matching the
            # title -> value hierarchy used elsewhere on the
            # dashboard (e.g. KPI cards).
            type_label = QLabel(ioc_type)
            type_label.setFont(fonts.caption())
            type_label.setStyleSheet(
                f"color: {palette.text_secondary}; font-weight: 600;"
            )

            count_label = QLabel(f"({value})")
            count_label.setFont(fonts.caption())
            count_label.setStyleSheet(
                f"color: {palette.text_muted};"
            )

            entry = QWidget()
            entry_layout = QHBoxLayout(entry)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(Spacing.XS)
            entry_layout.addWidget(
                swatch, 0, Qt.AlignmentFlag.AlignVCenter
            )
            entry_layout.addWidget(type_label)
            entry_layout.addWidget(count_label)
            entry_layout.addStretch()

            row, column = divmod(index, columns)
            legend_layout.addWidget(entry, row, column)

        # Even column widths so legend entries line up into a clean
        # grid instead of each column hugging its widest label.
        for column in range(columns):
            legend_layout.setColumnStretch(column, 1)

        self._display_layout.addWidget(bar_container)
        self._display_layout.addWidget(legend_container)