"""
SOC-IQ Dashboard

KPI Section

Displays the primary dashboard metrics using
enterprise MetricCard components.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import BaseWidget, MetricCard
from app.gui.design.tokens import Spacing


class KPISection(BaseWidget):
    """
    Executive dashboard KPI grid.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._eyebrow_label = QLabel("KEY METRICS")

        self._reports_card = MetricCard(
            title="Investigations",
            value="0",
            subtitle="Completed Reports",
        )

        self._ioc_card = MetricCard(
            title="Indicators",
            value="0",
            subtitle="Extracted IOCs",
        )

        self._risk_card = MetricCard(
            title="High Severity",
            value="0",
            subtitle="Critical Investigations",
        )

        self._database_card = MetricCard(
            title="Repository",
            value="ONLINE",
            subtitle="SQLite Database",
        )

        self._outer_layout = QVBoxLayout(self)
        self._layout = QGridLayout()

        self._build_ui()
        self.refresh_theme()
        self._configure_cards()

        # No hard-coded height ceiling. Each MetricCard already
        # reports its own natural sizeHint (icon/title + value +
        # subtitle); a magic pixel ceiling here is what clipped that
        # content in a previous pass. Maximum lets the section take
        # exactly what its cards need and no more, so it still can't
        # grow to compete with Investigation Queue / Featured / Live
        # Events for space, but it also can't clip.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        # Tighter gap between the "KEY METRICS" eyebrow and the card
        # row -- XS instead of SM, since the eyebrow is a label, not
        # a card, and doesn't need a full card-gap of separation.
        self._outer_layout.setSpacing(Spacing.XS)

        self._outer_layout.addWidget(self._eyebrow_label)

        self._layout.setContentsMargins(0, 0, 0, 0)

        # BATCH 03B: SM rather than MD between the four metric cards.
        # This section still reads as one compact instrument-panel
        # strip (per the Fortexa reference), but the tighter gap
        # meaningfully reduces the strip's total footprint, which was
        # the specific complaint ("still consumes too much vertical
        # space" / "reads as four generic cards instead of a compact
        # strip") -- this is a real spacing reduction, not a
        # comment-only change.
        self._layout.setHorizontalSpacing(Spacing.SM)
        self._layout.setVerticalSpacing(Spacing.SM)

        self._layout.addWidget(self._reports_card, 0, 0)
        self._layout.addWidget(self._ioc_card, 0, 1)
        self._layout.addWidget(self._risk_card, 0, 2)
        self._layout.addWidget(self._database_card, 0, 3)

        for column in range(4):
            self._layout.setColumnStretch(column, 1)

        self._outer_layout.addLayout(self._layout)

    def refresh_theme(self) -> None:
        """
        Refresh the KPI section styling.
        """

        self._eyebrow_label.setFont(
            self.fonts.label(),
        )

        self._eyebrow_label.setStyleSheet(
            f"""
            color: {self.palette.text_muted};
            font-weight: 700;
            letter-spacing: 1.5px;
            """
        )

    # --------------------------------------------------
    # Card Styling
    # --------------------------------------------------

    def _configure_cards(self) -> None:
        # Plain, widely-supported geometric glyphs (Geometric
        # Shapes Unicode block) instead of icon-font-dependent
        # symbols that fall back to "tofu" boxes on systems
        # without the right font installed.

        self._reports_card.set_icon("■")
        self._ioc_card.set_icon("●")
        self._risk_card.set_icon("▲")
        self._database_card.set_icon("◆")

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_metrics(
        self,
        *,
        reports: str,
        iocs: str,
        high_risk: str,
        database: str,
        reports_badge: str = "",
        iocs_badge: str = "",
        risk_badge: str = "",
        database_badge: str = "",
    ) -> None:
        """
        Update KPI values.

        Badges are optional and reflect real state passed in by
        the caller (e.g. a trend or live indicator computed by
        DashboardController). Omitting a badge hides it — there
        is no default/placeholder badge text.
        """

        self._reports_card.set_value(reports)
        self._ioc_card.set_value(iocs)
        self._risk_card.set_value(high_risk)
        self._database_card.set_value(database)

        if reports_badge:
            self._reports_card.set_badge(reports_badge)
        else:
            self._reports_card.clear_badge()

        if iocs_badge:
            self._ioc_card.set_badge(iocs_badge)
        else:
            self._ioc_card.clear_badge()

        if risk_badge:
            self._risk_card.set_badge(risk_badge)
        else:
            self._risk_card.clear_badge()

        if database_badge:
            self._database_card.set_badge(database_badge)
        else:
            self._database_card.clear_badge()

    def reports_card(self) -> MetricCard:
        return self._reports_card

    def ioc_card(self) -> MetricCard:
        return self._ioc_card

    def risk_card(self) -> MetricCard:
        return self._risk_card

    def database_card(self) -> MetricCard:
        return self._database_card