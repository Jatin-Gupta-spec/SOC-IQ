"""
SOC-IQ Design System

Live Security Events Widget

Displays the most recent investigations as a live-updating
feed, reused on the dashboard (or anywhere else a compact
"recent activity" surface is needed).
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.database.service import InvestigationService
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.status_badge import (
    BadgeType,
    StatusBadge,
)
from app.gui.design.tokens import Spacing

# NOTE: adjust this import to match wherever `event_bus` actually
# lives in the project layout (it was supplied as a standalone
# module in this review, with no importer to infer its real path
# from). It is assumed here to sit alongside the other GUI-facing
# singletons.
from app.gui.events.event_bus import event_bus

logger = logging.getLogger(__name__)


_SEVERITY_BADGE_MAP: dict[str, BadgeType] = {
    "critical": BadgeType.CRITICAL,
    "high": BadgeType.HIGH,
    "medium": BadgeType.MEDIUM,
    "low": BadgeType.LOW,
}


class LiveSecurityEventsWidget(ModernCard):
    """
    Live-updating feed of the most recent investigations.

    Purely presentational: all data access is delegated to
    `InvestigationService`, and the widget only re-renders
    in response to `event_bus.investigation_created` — it
    contains no business logic of its own.
    """

    _MAX_EVENTS = 5

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._investigation_service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )

        self._events_layout = QVBoxLayout()
        self._events_layout.setSpacing(Spacing.SM)

        self._empty_state_label = self._build_empty_state_label()

        self._build_ui()
        self._connect_signals()

        self.refresh()

    # --------------------------------------------------
    # Construction
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Assemble the static chrome around the event list.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        header_layout = QHBoxLayout()
        header_layout.setSpacing(Spacing.SM)

        title_label = QLabel("Live Security Events")
        title_label.setFont(fonts.title())
        title_label.setStyleSheet(
            f"color: {palette.text_primary}; background: transparent;"
        )

        subtitle_label = QLabel("Most recent investigations")
        subtitle_label.setFont(fonts.caption())
        subtitle_label.setStyleSheet(
            f"color: {palette.text_secondary}; background: transparent;"
        )

        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(0)
        header_text_layout.addWidget(title_label)
        header_text_layout.addWidget(subtitle_label)

        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        self.add_layout(header_layout)
        self.add_layout(self._events_layout)
        self.add_stretch()

    def _build_empty_state_label(self) -> QLabel:
        """
        Build the label shown when there are no
        investigations to display.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        label = QLabel(
            "No security events available.\n"
            "Analyze a report to begin monitoring."
        )

        label.setFont(fonts.body())
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {palette.text_secondary}; background: transparent;"
        )

        return label

    def _connect_signals(self) -> None:
        """
        Subscribe to the events that should trigger a
        refresh of the feed.
        """

        event_bus.investigation_created.connect(
            self.refresh,
        )

    # --------------------------------------------------
    # Data / Refresh
    # --------------------------------------------------

    def refresh(self) -> None:
        """
        Reload the most recent investigations and
        re-render the feed.
        """

        try:

            investigations = self._investigation_service.find_recent(
                self._MAX_EVENTS,
            )

        except Exception as exc:

            logger.exception(
                "Failed to load live security events: %s",
                exc,
            )

            investigations = []

        self._render(investigations)

    def _render(
        self,
        investigations: list[Investigation],
    ) -> None:
        """
        Rebuild the event list UI from the given
        investigations.
        """

        self._clear_events()

        if not investigations:
            self._events_layout.addWidget(
                self._empty_state_label,
            )
            return

        for investigation in investigations:
            self._events_layout.addWidget(
                self._build_event_row(investigation),
            )

    def _clear_events(self) -> None:
        """
        Remove all currently displayed event rows
        (and the empty-state label, if present).
        """

        while self._events_layout.count():

            item = self._events_layout.takeAt(0)
            widget = item.widget()

            if widget is None:
                continue

            widget.setParent(None)

    # --------------------------------------------------
    # Row Construction
    # --------------------------------------------------

    def _build_event_row(
        self,
        investigation: Investigation,
    ) -> QWidget:
        """
        Build a single event row for one investigation.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        row = QWidget()

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(Spacing.MD)

        badge_type = _SEVERITY_BADGE_MAP.get(
            (investigation.severity or "").lower(),
            BadgeType.DEFAULT,
        )

        severity_badge = StatusBadge(
            (investigation.severity or "Unknown").title(),
            badge_type,
        )

        details_layout = QVBoxLayout()
        details_layout.setSpacing(2)

        report_label = QLabel(investigation.report_name or "Untitled report")
        report_label.setFont(fonts.body())
        report_label.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 600; background: transparent;"
        )

        timestamp_label = QLabel(
            self._format_timestamp(investigation.analyzed_at)
        )
        timestamp_label.setFont(fonts.caption())
        timestamp_label.setStyleSheet(
            f"color: {palette.text_secondary}; background: transparent;"
        )

        details_layout.addWidget(report_label)
        details_layout.addWidget(timestamp_label)

        risk_label = QLabel(
            self._format_risk_score(investigation.risk_score)
        )
        risk_label.setFont(fonts.body())
        risk_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        risk_label.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 600; background: transparent;"
        )

        row_layout.addWidget(severity_badge)
        row_layout.addLayout(details_layout, 1)
        row_layout.addWidget(risk_label)

        return row

    @staticmethod
    def _format_timestamp(analyzed_at: object) -> str:
        """
        Format an investigation's analysis timestamp for
        display, defensively handling either a `datetime`
        or an already-serialized value.
        """

        if isinstance(analyzed_at, datetime):
            return analyzed_at.strftime("%Y-%m-%d %H:%M")

        if analyzed_at:
            return str(analyzed_at)

        return "Unknown time"

    @staticmethod
    def _format_risk_score(risk_score: object) -> str:
        """
        Format an investigation's risk score for display.
        """

        if risk_score is None:
            return "Risk: N/A"

        return f"Risk: {risk_score} / 100"

    def closeEvent(self, event):
        try:
            event_bus.investigation_created.disconnect(self.refresh)
        except (RuntimeError, TypeError):
            pass

        super().closeEvent(event)