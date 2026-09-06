"""
IOC Detail dialog for the SOC-IQ desktop application.

Shows the full investigation context for a single selected IOC:
its value/type, which investigation it belongs to, its risk
significance, and its threat-intelligence status -- reusing the
existing design-system widgets (`DetailSection`, `KeyValueRow`,
`StatusBadge`) rather than introducing new styling.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.services.ioc_detail_context import (
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
)
from app.gui.components.feedback.status_badge import StatusBadge
from app.gui.utils.badge_mapping import (
    severity_to_badge_type,
    ti_state_to_badge_type,
)
from app.gui.widgets.detail_section import DetailSection
from app.gui.widgets.key_value_row import KeyValueRow


class IOCDetailDialog(QDialog):
    """
    Displays the full investigation/threat-intelligence context
    for a single selected IOC value.
    """

    # Emitted when the analyst asks to jump from an enriched
    # indicator to its full threat-intelligence record. Carries the
    # SHA256 hash; the workspace page is responsible for actually
    # switching tabs/selecting the row, reusing the same drill-down
    # wired up for the "Extracted IOCs" table in Part 1.
    threat_intel_requested = Signal(str)

    _TI_STATE_LABELS = {
        TI_STATE_ENRICHED: "Enriched",
        TI_STATE_NOT_ENRICHED: "Not Enriched",
        TI_STATE_NO_API_KEY: "API Key Not Configured",
        TI_STATE_PROVIDER_ERROR: "Provider Error",
        TI_STATE_INCOMPLETE_CHECK: "Check Incomplete",
        TI_STATE_UNSUPPORTED_TYPE: "Not Supported",
    }

    def __init__(
        self,
        context: dict[str, Any],
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._context = context

        self.setWindowTitle("IOC Details")

        self.resize(560, 520)

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the dialog layout from the supplied context.
        """

        layout = QVBoxLayout()

        layout.setSpacing(16)

        layout.addWidget(self._build_indicator_section())
        layout.addWidget(self._build_investigation_section())
        layout.addWidget(self._build_threat_intel_section())

        layout.addStretch()

        layout.addLayout(self._build_button_row())

        self.setLayout(layout)

    def _build_indicator_section(self) -> DetailSection:
        """
        Build the "what is this indicator" section.
        """

        section = DetailSection(
            "Indicator",
            "The selected indicator of compromise.",
        )

        value_row = KeyValueRow(
            "Value",
            self._context["value"],
        )

        type_row = KeyValueRow(
            "Type",
            self._context["ioc_type_title"],
        )

        section.add_widget(value_row)
        section.add_widget(type_row)

        significance_row_layout = QHBoxLayout()

        significance_label = QLabel("Risk Significance")

        significance_label.setObjectName("keyValueKey")

        significance_badge = StatusBadge(
            self._context["significance"].upper(),
            badge_type=severity_to_badge_type(self._context["significance"]),
        )

        significance_row_layout.addWidget(significance_label)
        significance_row_layout.addStretch()
        significance_row_layout.addWidget(significance_badge)

        significance_row = QVBoxLayout()

        significance_row.addLayout(significance_row_layout)

        significance_note = QLabel(
            "Reflects how heavily this indicator category weighs "
            "into the investigation's overall risk score."
        )

        significance_note.setWordWrap(True)

        significance_row.addWidget(significance_note)

        section.content_layout().addLayout(significance_row)

        return section

    def _build_investigation_section(self) -> DetailSection:
        """
        Build the "which investigation" context section.
        """

        section = DetailSection(
            "Investigation Context",
            "The investigation this indicator was extracted from.",
        )

        investigation = self._context["investigation"]

        investigation_id = investigation["investigation_id"]

        section.add_widget(
            KeyValueRow(
                "Investigation ID",
                (
                    str(investigation_id)
                    if investigation_id is not None
                    else "Unsaved"
                ),
            )
        )

        section.add_widget(
            KeyValueRow(
                "Report Name",
                investigation["report_name"],
            )
        )

        analyzed_at = investigation["analyzed_at"]

        section.add_widget(
            KeyValueRow(
                "Analyzed",
                (
                    analyzed_at.strftime("%Y-%m-%d %H:%M UTC")
                    if analyzed_at is not None
                    else "Unknown"
                ),
            )
        )

        section.add_widget(
            KeyValueRow(
                "Investigation Status",
                investigation["status"],
            )
        )

        return section

    def _build_threat_intel_section(self) -> DetailSection:
        """
        Build the threat-intelligence status section.
        """

        section = DetailSection(
            "Threat Intelligence",
            "Enrichment status for this indicator.",
        )

        threat_intel = self._context["threat_intel"]

        state = threat_intel["state"]

        state_row_layout = QHBoxLayout()

        state_label = QLabel("Status")

        state_label.setObjectName("keyValueKey")

        state_badge = StatusBadge(
            self._TI_STATE_LABELS.get(state, state).upper(),
            badge_type=ti_state_to_badge_type(state),
        )

        state_row_layout.addWidget(state_label)
        state_row_layout.addStretch()
        state_row_layout.addWidget(state_badge)

        section.content_layout().addLayout(state_row_layout)

        if state == TI_STATE_ENRICHED:

            record = threat_intel["record"]

            section.add_widget(
                KeyValueRow(
                    "Verdict",
                    str(record.get("verdict", "Unknown")),
                )
            )

            section.add_widget(
                KeyValueRow(
                    "Detection Ratio",
                    str(record.get("detection_ratio", "N/A")),
                )
            )

            reputation = record.get("reputation")

            section.add_widget(
                KeyValueRow(
                    "Reputation",
                    (
                        str(reputation)
                        if reputation is not None
                        else "Unavailable"
                    ),
                )
            )

            last_analysis_date = record.get("last_analysis_date")

            section.add_widget(
                KeyValueRow(
                    "Last Analysis",
                    (
                        str(last_analysis_date)
                        if last_analysis_date is not None
                        else "Unavailable"
                    ),
                )
            )

            self._view_record_button = QPushButton(
                "View Full Threat Intelligence Record",
            )

            self._view_record_button.clicked.connect(
                self._on_view_record_clicked,
            )

            section.content_layout().addWidget(
                self._view_record_button,
            )

        else:

            message_label = QLabel(threat_intel["message"])

            message_label.setWordWrap(True)

            section.content_layout().addWidget(message_label)

        return section

    def _build_button_row(self) -> QHBoxLayout:
        """
        Build the dialog's bottom button row.
        """

        button_row = QHBoxLayout()

        button_row.addStretch()

        close_button = QPushButton("Close")

        close_button.clicked.connect(self.accept)

        button_row.addWidget(close_button)

        return button_row

    def _on_view_record_clicked(self) -> None:
        """
        Request navigation to the full threat-intelligence record
        and close this dialog so the analyst lands on it directly,
        rather than leaving a stale detail dialog open on top of
        the Threat Intelligence tab.
        """

        self.threat_intel_requested.emit(
            self._context["value"],
        )

        self.accept()
