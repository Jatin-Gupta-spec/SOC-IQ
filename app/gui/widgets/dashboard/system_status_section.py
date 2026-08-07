"""
SOC-IQ Dashboard

System Status Section

Displays operational health information for
SOC-IQ services.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import (
    Panel,
    SectionHeader,
    StatusBadge,
)
from app.gui.components.feedback.status_badge import BadgeType
from app.gui.design.tokens import Spacing

# Statuses that should render as healthy / degraded / down. Anything
# reported by the health service that isn't recognized falls back to
# BadgeType.DEFAULT rather than being assumed healthy — a status
# panel that defaults to "green" on unrecognized input can mask a
# real outage, which defeats the purpose of this panel.
_HEALTHY_STATUSES = {"connected", "operational", "healthy", "up", "online"}
_DEGRADED_STATUSES = {"degraded", "slow", "warning", "reconnecting"}
_DOWN_STATUSES = {"disconnected", "down", "offline", "error", "failed"}


class SystemStatusSection(QWidget):
    """
    Dashboard system status section.

    Displays live health information for each monitored service, as
    reported by DashboardController.get_system_status(). Call
    load_status() with that dict to populate the panels — until
    then, every panel shows "Unknown" rather than a hardcoded
    healthy-looking state.

    Displays:

    • Database status
    • Threat Intelligence status
    """

    # Each entry describes one monitored service panel: its display
    # title/subtitle, and the keys load_status() reads from the
    # status dict for it. Adding a new monitored service (e.g. a
    # second threat-intel provider) only requires one new entry here
    # — no new panel-building method to copy-paste.
    #
    # status_key values match the keys SystemHealthService.get_status()
    # actually returns ("database", "virustotal", ...) — a flat
    # {name: status_string} dict with no per-service detail/timestamp
    # data. detail_key/updated_key are kept pointing at keys the
    # service does not currently provide, so those rows fall back to
    # their "--" placeholder rather than being removed outright; if
    # SystemHealthService is ever extended to report detail/timestamp
    # data, point these at the new keys.
    _SERVICES = (
        {
            "id": "database",
            "title": "Database Health",
            "subtitle": "Repository status",
            "status_key": "database",
            "detail_key": "database_detail",
            "updated_key": "database_updated",
        },
        {
            "id": "threat_intelligence",
            "title": "Threat Intelligence",
            "subtitle": "External providers",
            "status_key": "virustotal",
            "detail_key": "threat_intel_detail",
            "updated_key": "threat_intel_updated",
        },
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._panels: dict[str, dict[str, QWidget]] = {}

        self._layout = QGridLayout(self)

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(Spacing.LG)
        self._layout.setVerticalSpacing(Spacing.LG)

        for column, service in enumerate(self._SERVICES):

            panel, widgets = self._create_status_panel(
                service["title"],
                service["subtitle"],
            )

            self._panels[service["id"]] = widgets

            self._layout.addWidget(panel, 0, column)
            self._layout.setColumnStretch(column, 1)

    def _create_status_panel(
        self,
        title: str,
        subtitle: str,
    ) -> tuple[QWidget, dict[str, QWidget]]:
        """
        Build a single status panel and return it along with
        references to the widgets load_status() updates.
        """

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
            SectionHeader(title, subtitle)
        )

        badge = StatusBadge("Unknown", BadgeType.DEFAULT)
        layout.addWidget(badge)

        detail_label = QLabel("--")
        layout.addWidget(detail_label)

        updated_label = QLabel("Last Update: --")
        layout.addWidget(updated_label)

        layout.addStretch()

        return panel, {
            "badge": badge,
            "detail": detail_label,
            "updated": updated_label,
        }

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def load_status(
        self,
        status: dict[str, str],
    ) -> None:
        """
        Populate the panels with live system status.

        Expects the dict returned by
        DashboardController.get_system_status(). Each service's
        status text is matched (case-insensitively) against known
        healthy/degraded/down states to pick the badge color. A
        missing or unrecognized status renders as "Unknown" rather
        than silently defaulting to a healthy-looking badge.
        """

        for service in self._SERVICES:

            widgets = self._panels[service["id"]]

            status_text = status.get(
                service["status_key"],
                "Unknown",
            )

            self._apply_panel_status(
                widgets,
                status_text=status_text,
                detail_text=status.get(service["detail_key"], "--"),
                updated_text=status.get(service["updated_key"], "--"),
            )

    def _apply_panel_status(
        self,
        widgets: dict[str, QWidget],
        *,
        status_text: str,
        detail_text: str,
        updated_text: str,
    ) -> None:

        widgets["badge"].set_text(status_text)
        widgets["badge"].set_badge_type(
            self._badge_type_for_status(status_text)
        )

        widgets["detail"].setText(detail_text)
        widgets["updated"].setText(f"Last Update: {updated_text}")

    @staticmethod
    def _badge_type_for_status(status_text: str) -> BadgeType:
        """
        Map a raw status string to a badge color.

        Falls back to BadgeType.DEFAULT for anything unrecognized
        instead of assuming healthy — an unknown status should never
        render as green.
        """

        normalized = status_text.strip().lower()

        if normalized in _HEALTHY_STATUSES:
            return BadgeType.LOW

        if normalized in _DEGRADED_STATUSES:
            return BadgeType.MEDIUM

        if normalized in _DOWN_STATUSES:
            return BadgeType.CRITICAL

        return BadgeType.DEFAULT