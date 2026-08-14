"""
SOC-IQ Dashboard

Featured Investigation Card

Enterprise investigation summary card displayed on the
SOC dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.status_badge import (
    BadgeType,
    StatusBadge,
)
from app.gui.design.tokens import Spacing


class FeaturedInvestigationCard(ModernCard):
    """
    Enterprise featured investigation card.
    """

    # TODO: identical to ThreatIntelligenceFeedWidget._SEVERITY_BADGE_MAP.
    # Hoist to a single shared constant (e.g. in status_badge.py) next
    # time that module is touched, so the severity->badge mapping has
    # one source of truth instead of two copies that can drift.
    _SEVERITY_BADGE_MAP = {
        "LOW": BadgeType.LOW,
        "MEDIUM": BadgeType.MEDIUM,
        "HIGH": BadgeType.HIGH,
        "CRITICAL": BadgeType.CRITICAL,
        "INFO": BadgeType.INFO,
    }

    open_workspace_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(parent)

        self._investigation: Investigation | None = None

        # BATCH 03B: explicit Expanding/Expanding so the card fully
        # occupies whatever height primary_row's stretch factor gives
        # it in dashboard_page.py, rather than relying on ModernCard's
        # default and settling at a smaller natural size that then
        # leaves the button-anchoring addStretch() below with less
        # room than the row actually has available.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        self._title_label = QLabel(
            "Latest Investigation"
        )

        self._severity_badge = StatusBadge(
            "NONE",
            BadgeType.DEFAULT,
        )

        # --------------------------------------------------
        # Main Content
        # --------------------------------------------------

        self._report_name_label = QLabel(
            "No Investigation Available"
        )

        self._ioc_label = QLabel(
            "IOC Count : --"
        )

        self._risk_label = QLabel(
            "Risk Score : -- / 100"
        )

        self._date_label = QLabel(
            "Analysis Time : --"
        )

        # --------------------------------------------------
        # Risk Progress
        # --------------------------------------------------

        self._risk_bar = QProgressBar()

        self._risk_bar.setMinimum(0)
        self._risk_bar.setMaximum(100)
        self._risk_bar.setValue(0)
        self._risk_bar.setTextVisible(False)
        self._risk_bar.setFixedHeight(10)

        # --------------------------------------------------
        # Action Button
        # --------------------------------------------------

        self._open_button = AnimatedButton(
            "Open Workspace"
        )

        self._build_card_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_card_ui(self) -> None:
        """
        Build the featured investigation card.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title_label.setFont(
            fonts.caption()
        )

        self._title_label.setStyleSheet(
            f"""
            color:{palette.text_muted};
            font-weight:700;
            letter-spacing:1px;
            text-transform:uppercase;
            """
        )

        self._report_name_label.setFont(
            fonts.heading()
        )

        self._report_name_label.setWordWrap(True)

        self._report_name_label.setStyleSheet(
            f"""
            color:{palette.text_primary};
            """
        )

        for label in (
            self._ioc_label,
            self._date_label,
        ):

            label.setFont(
                fonts.body()
            )

            label.setStyleSheet(
                f"color:{palette.text_secondary};"
            )

        self._risk_label.setFont(
            fonts.body()
        )

        self._risk_label.setStyleSheet(
            f"""
            color:{palette.brand_primary};
            font-weight:700;
            """
        )

        self._risk_bar.setStyleSheet(
            self._progress_bar_stylesheet(
                palette.brand_primary
            )
        )

        header_layout = QHBoxLayout()

        header_layout.addWidget(
            self._title_label
        )

        header_layout.addStretch()

        header_layout.addWidget(
            self._severity_badge
        )

        info_layout = QVBoxLayout()

        # BATCH 03B: XS rather than SM between the info rows
        # (report name / IOC count / risk score+bar / date). This is
        # a real content-density change, not the addStretch() below
        # -- it reduces the info block's own natural height, which
        # is what leaves the button more room to render uncompressed
        # inside a card whose total height it doesn't control.
        info_layout.setSpacing(
            Spacing.XS
        )

        info_layout.addWidget(
            self._report_name_label
        )

        info_layout.addWidget(
            self._ioc_label
        )

        info_layout.addWidget(
            self._risk_label
        )

        info_layout.addWidget(
            self._risk_bar
        )

        info_layout.addWidget(
            self._date_label
        )

        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self._open_button.setEnabled(False)

        self._open_button.clicked.connect(
            self.open_workspace_requested.emit
        )

        button_layout.addWidget(
            self._open_button
        )

        # All sections are assembled into one local `card_layout`
        # (spacing explicitly set to 0) which is then added to
        # ModernCard's content_layout() via a single add_layout()
        # call, so content_layout()'s own automatic spacing never
        # compounds with the addSpacing()/addStretch() calls below --
        # every gap here is controlled purely at exactly its token
        # value.
        card_layout = QVBoxLayout()
        card_layout.setSpacing(0)

        card_layout.addLayout(
            header_layout
        )

        # BATCH 03B: XS rather than SM (see info_layout note above --
        # same reasoning, this is the header-to-info gap).
        card_layout.addSpacing(
            Spacing.XS
        )

        card_layout.addLayout(
            info_layout
        )

        # Root cause of both the dead-space and button-clipping
        # complaints previously: the card can get more vertical
        # height than its content needs, but there was no stretch
        # item to absorb that extra space. Placing addStretch() here
        # makes the info block sit at its natural size at the top
        # and lets any extra height self-collapse to zero when the
        # row is short, while the info block itself is now shorter
        # (tighter spacing above) so there's more slack before the
        # button is the thing that has to give.
        card_layout.addStretch()

        # BATCH 03B: SM rather than MD before the button -- the last
        # remaining bit of padding trimmed to give the button the
        # most room possible in a short row without touching the
        # button's own geometry.
        card_layout.addSpacing(
            Spacing.SM
        )

        card_layout.addLayout(
            button_layout
        )

        self.add_layout(
            card_layout
        )

    def _progress_bar_stylesheet(self, chunk_color: str) -> str:
        """
        Build the QProgressBar QSS for the risk bar.

        Shared by both the initial (neutral) style set in
        _build_card_ui() and the severity-driven style applied by
        _apply_risk_bar_color(), so the two call sites can't drift
        apart -- only the chunk color varies between them; the
        track color, border, and radius are identical either way.
        """

        palette = self.theme.palette

        return f"""
        QProgressBar {{
            background: {palette.surface_secondary};
            border: none;
            border-radius: 5px;
        }}

        QProgressBar::chunk {{
            background: {chunk_color};
            border-radius: 5px;
        }}
        """

    def _apply_risk_bar_color(self, color: str) -> None:
        """
        Style the risk bar using the given color.
        """

        self._risk_bar.setStyleSheet(
            self._progress_bar_stylesheet(color)
        )


    def _risk_bar_color_for_severity(self, severity: str) -> str:
        """
        Return the appropriate color for the investigation severity.
        """

        palette = self.theme.palette

        mapping = {
            "LOW": palette.severity_low,
            "MEDIUM": palette.severity_medium,
            "HIGH": palette.severity_high,
            "CRITICAL": palette.severity_critical,
        }

        return mapping.get(
            severity,
            palette.brand_primary,
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def load_investigation(
        self,
        investigation: Investigation | None,
    ) -> None:
        """
        Load the latest investigation.
        """

        self._investigation = investigation

        if investigation is None:

            self._report_name_label.setText(
                "No Investigation Available"
            )

            self._ioc_label.setText(
                "IOC Count : --"
            )

            self._risk_label.setText(
                "Risk Score : -- / 100"
            )

            self._risk_bar.setValue(0)

            self._date_label.setText(
                "Analysis Time : --"
            )

            self._severity_badge.set_text(
                "NONE"
            )

            self._severity_badge.set_badge_type(
                BadgeType.DEFAULT
            )

            self._open_button.setEnabled(
                False
            )

            return

        self._report_name_label.setText(
            investigation.report_name
        )

        ioc_count = sum(
            len(values)
            for values in investigation.iocs.values()
        )

        self._ioc_label.setText(
            f"IOC Count : {ioc_count}"
        )

        self._risk_label.setText(
            f"Risk Score : {investigation.risk_score} / 100"
        )

        severity = (
            investigation.severity or "INFO"
        ).upper()

        self._risk_bar.setValue(
            investigation.risk_score
        )

        self._apply_risk_bar_color(
            self._risk_bar_color_for_severity(
                severity
            )
        )

        self._date_label.setText(
            "Analysis Time : "
            + investigation.analyzed_at.strftime(
                "%d %b %Y  %H:%M"
            )
        )

        self._severity_badge.set_text(
            severity
        )

        self._severity_badge.set_badge_type(
            self._SEVERITY_BADGE_MAP.get(
                severity,
                BadgeType.DEFAULT,
            )
        )

        self._open_button.setEnabled(
            True
        )