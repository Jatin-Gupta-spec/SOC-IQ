"""
SOC-IQ Dashboard

Activity Section

Displays recent investigations and
activity timeline.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QGridLayout,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import (
    Panel,
    SectionHeader,
    TimelineEvent,
    TimelineWidget,
)
from app.gui.design.tokens import Spacing


class ActivitySection(QWidget):
    """
    Dashboard activity section.

    Displays:

    • Recent investigations
    • Activity timeline
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._layout = QGridLayout(self)

        self._timeline = TimelineWidget()
        self._investigation_list = QListWidget()

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(Spacing.LG)
        self._layout.setVerticalSpacing(Spacing.LG)

        self._layout.addWidget(
            self._create_recent_panel(),
            0,
            0,
        )

        self._layout.addWidget(
            self._create_timeline_panel(),
            0,
            1,
        )

        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

    def _create_recent_panel(self) -> QWidget:

        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "Recent Investigations",
                "Latest completed analyses",
            )
        )

        self._populate_recent()

        layout.addWidget(self._investigation_list)

        return panel

    def _create_timeline_panel(self) -> QWidget:

        panel = Panel()

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "Activity Timeline",
                "Recent system events",
            )
        )

        self._populate_timeline()

        layout.addWidget(self._timeline)

        return panel

    # --------------------------------------------------
    # Placeholder Data
    # --------------------------------------------------

    def _populate_recent(self) -> None:

        investigations = [
            "Emotet_Report.pdf",
            "Lumma_Stealer.docx",
            "AgentTesla.zip",
            "DarkGate.exe",
            "Phishing_Email.msg",
        ]

        for report in investigations:
            QListWidgetItem(report, self._investigation_list)

    def _populate_timeline(self) -> None:

        self._timeline.add_event(
            TimelineEvent(
                timestamp="09:12",
                title="Analysis Complete",
                description="Parsed Lumma_Stealer.docx",
            )
        )

        self._timeline.add_event(
            TimelineEvent(
                timestamp="09:30",
                title="IOC Extraction",
                description="142 indicators extracted",
            )
        )

        self._timeline.add_event(
            TimelineEvent(
                timestamp="09:42",
                title="Threat Intelligence",
                description="VirusTotal enrichment finished",
            )
        )