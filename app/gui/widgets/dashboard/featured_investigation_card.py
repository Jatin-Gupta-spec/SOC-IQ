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

    open_workspace_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(parent)

        self._investigation: Investigation | None = None

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

        self._family_label = QLabel(
            "Malware Family : Unknown"
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
            fonts.title()
        )

        self._report_name_label.setWordWrap(True)

        self._report_name_label.setStyleSheet(
            f"""
            color:{palette.text_primary};
            font-size:22px;
            font-weight:700;
            """
        )

        for label in (
            self._family_label,
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
            f"""
            QProgressBar{{
                background:{palette.surface_secondary};
                border:none;
                border-radius:5px;
            }}

            QProgressBar::chunk{{
                background:{palette.brand_primary};
                border-radius:5px;
            }}
            """
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

        info_layout.setSpacing(
            Spacing.SM
        )

        info_layout.addWidget(
            self._report_name_label
        )

        info_layout.addWidget(
            self._family_label
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

        self.add_layout(
            header_layout
        )

        self.add_spacing(
            Spacing.SM
        )

        self.add_layout(
            info_layout
        )

        self.add_spacing(
            Spacing.MD
        )

        self.add_layout(
            button_layout
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

            self._family_label.setText(
                "Malware Family : Unknown"
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

        self._family_label.setText(
            "Malware Family : Unknown"
        )

        self._risk_label.setText(
            f"Risk Score : {investigation.risk_score} / 100"
        )

        self._risk_bar.setValue(
            investigation.risk_score
        )

        self._date_label.setText(
            "Analysis Time : "
            + investigation.analyzed_at.strftime(
                "%d %b %Y  %H:%M"
            )
        )

        severity = (
            investigation.severity or "INFO"
        ).upper()

        mapping = {
            "LOW": BadgeType.LOW,
            "MEDIUM": BadgeType.MEDIUM,
            "HIGH": BadgeType.HIGH,
            "CRITICAL": BadgeType.CRITICAL,
            "INFO": BadgeType.INFO,
        }

        self._severity_badge.set_text(
            severity
        )

        self._severity_badge.set_badge_type(
            mapping.get(
                severity,
                BadgeType.DEFAULT,
            )
        )

        self._open_button.setEnabled(
            True
        )