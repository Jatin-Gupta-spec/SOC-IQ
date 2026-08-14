"""
SOC-IQ Dashboard

System Status Section

Displays operational health information for
SOC-IQ services.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import StatusBadge
from app.gui.components.feedback.status_badge import BadgeType
from app.gui.design.tokens import Colors, Radius, Spacing, Typography

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

        self.setObjectName("systemStatusSection")

        # "SYSTEM STATUS" eyebrow, styled to match KPISection's own
        # eyebrow ("KEY METRICS") exactly -- same font token, same
        # color/weight/letter-spacing -- so the two utility-band
        # widgets read as one group instead of KPI looking labeled
        # and this one looking orphaned.
        self._eyebrow_label = QLabel("SYSTEM STATUS")

        # Outer layout now holds [eyebrow, status-row layout] rather
        # than being the status-row QHBoxLayout directly -- the
        # eyebrow needs to sit above the rows, and this is the same
        # outer-layout-plus-sub-layout shape KPISection already uses
        # for its own eyebrow. self._layout keeps its original
        # meaning (the two-service status row) so load_status() and
        # friends are unaffected.
        self._outer_layout = QVBoxLayout(self)
        self._layout = QHBoxLayout()

        self._build_ui()
        self._apply_grouped_styling()

        # No hard-coded height ceiling. A magic 40px number is what
        # clips once the grouped-utility padding below is added; a
        # Maximum size policy still keeps this row from ever
        # growing to compete with Investigation Queue / Featured /
        # Live Events for space, it just does so relative to this
        # row's own natural (label + badge + padding) sizeHint
        # instead of a fixed pixel guess.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

    @staticmethod
    def _build_font(style) -> QFont:
        """
        Build a QFont from a Typography TextStyle token.

        This widget extends plain QWidget rather than BaseWidget
        (unlike every other file in this audit), so it has no
        `self.fonts`/`self.palette` runtime theme accessor. Rather
        than inventing one or changing the base class, this builds
        directly from the same Typography/Colors token modules
        every other widget's theme is ultimately built from.
        """

        font = QFont(style.family, style.size)
        font.setWeight(QFont.Weight(style.weight))
        return font

    def _apply_grouped_styling(self) -> None:
        """
        Subtle grouped-utility treatment: a faint, theme-agnostic
        panel background so the two status rows read as one
        cohesive strip rather than floating labels -- without
        reintroducing the old two-Panel layout.
        """

        self.setStyleSheet(
            f"""
            QWidget#systemStatusSection {{
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: {Radius.CARD}px;
            }}
            """
        )

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Build a compact "SYSTEM STATUS" eyebrow above a horizontal
        status strip: one label/badge pair per monitored service,
        e.g.

            SYSTEM STATUS
            Database: Operational    Threat Intelligence: Operational

        Replaces the previous two-Panel layout (SectionHeader +
        badge + permanently-placeholder detail/updated labels),
        which cost far more vertical space than the flat status
        data actually justified.
        """

        self._outer_layout.setContentsMargins(
            Spacing.LG,
            Spacing.SM,
            Spacing.LG,
            Spacing.SM,
        )
        self._outer_layout.setSpacing(Spacing.SM)

        self._eyebrow_label.setFont(
            self._build_font(Typography.LABEL)
        )
        self._eyebrow_label.setStyleSheet(
            f"""
            color: {Colors.Text.MUTED};
            font-weight: 700;
            letter-spacing: 1.5px;
            """
        )
        self._outer_layout.addWidget(self._eyebrow_label)

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.LG)

        for service in self._SERVICES:

            row, widgets = self._create_status_row(
                service["title"],
            )

            self._panels[service["id"]] = widgets

            self._layout.addLayout(row)

        self._layout.addStretch()

        self._outer_layout.addLayout(self._layout)

    def _create_status_row(
        self,
        title: str,
    ) -> tuple[QHBoxLayout, dict[str, QWidget]]:
        """
        Build a single compact "<title>: <status>" row and return
        it along with references to the widgets load_status()
        updates.
        """

        row = QHBoxLayout()
        row.setSpacing(Spacing.SM)

        label = QLabel(f"{title}:")
        label.setFont(self._build_font(Typography.BODY))
        label.setStyleSheet(
            f"color: {Colors.Text.SECONDARY};"
        )
        row.addWidget(label)

        badge = StatusBadge("Unknown", BadgeType.DEFAULT)
        row.addWidget(badge)

        return row, {
            "label": label,
            "badge": badge,
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

            # detail_key/updated_key stay in _SERVICES (data-driven
            # definition preserved) but are intentionally not read
            # here -- the backend does not supply real values for
            # them today, and the compact strip correctly avoids
            # inventing/displaying placeholder "--" content.

            self._apply_panel_status(
                widgets,
                status_text=status_text,
            )

    def _apply_panel_status(
        self,
        widgets: dict[str, QWidget],
        *,
        status_text: str,
    ) -> None:

        widgets["badge"].set_text(status_text)
        widgets["badge"].set_badge_type(
            self._badge_type_for_status(status_text)
        )

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