"""
Reusable IOC summary widget for the SOC-IQ desktop application.

This widget displays all extracted Indicators of Compromise
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.components.feedback.empty_state import EmptyState
from app.gui.components.feedback.status_badge import StatusBadge
from app.gui.design.tokens import Spacing
from app.gui.utils.badge_mapping import severity_to_badge_type
from app.services.ioc_significance import ioc_type_significance

# All four Phase 3E categories carry threat-intelligence
# enrichment -- kept in sync with
# `app.services.ioc_detail_context._ENRICHABLE_IOC_TYPES`. This
# widget only needs the category set, not the full context
# machinery, so it is not imported from there to avoid pulling in
# an unrelated dependency for one constant.
_ENRICHABLE_IOC_TYPES = frozenset({"sha256", "ipv4", "domains", "urls"})

# Shown in the Threat Intelligence column for any category outside
# `_ENRICHABLE_IOC_TYPES` (i.e. one the current provider
# integration does not enrich at all -- see `ThreatIntelService`).
# Matches the vocabulary already used by `IOCDetailDialog` for the
# same state.
_TI_NOT_SUPPORTED_LABEL = "Not Supported"

# Shown for an enrichable category when no investigation-level
# threat-intelligence overview was supplied by the caller (e.g. a
# page that does not compute one). Distinct from "Not Supported":
# here enrichment *does* apply to this category, the overview just
# isn't known.
_TI_UNKNOWN_LABEL = "\u2014"


class IOCSummaryWidget(QWidget):
    """
    Displays extracted Indicators of Compromise.
    """

    ioc_selected = Signal(
        str,
        list,
    )

    IOC_TITLES = {
        "ipv4": "IPv4 Addresses",
        "domains": "Domains",
        "urls": "URLs",
        "emails": "Emails",
        "md5": "MD5 Hashes",
        "sha1": "SHA1 Hashes",
        "sha256": "SHA256 Hashes",
        "cves": "CVEs",
        "windows_file_paths": "Windows File Paths",
        "windows_registry_keys": "Registry Keys",
    }

    # Column indices for the summary table. Named rather than
    # hardcoded at each call site, matching the convention already
    # used by `IOCDetailsWidget`/`InvestigationWorkspacePage`.
    _COLUMN_TYPE = 0
    _COLUMN_COUNT = 1
    _COLUMN_SIGNIFICANCE = 2
    _COLUMN_THREAT_INTEL = 3

    def __init__(self) -> None:
        super().__init__()

        self._ioc_data: dict[str, list[str]] = {}

        # Result of `build_investigation_threat_intel_overview()`
        # for the investigation currently on display, if the caller
        # supplied one -- see `load_investigation()`. Drives the
        # Threat Intelligence column's SHA256 row.
        self._threat_intel_overview: dict | None = None

        # Shown instead of the (all-zero) table when an investigation
        # genuinely produced no IOCs of any type, so the analyst sees
        # "no evidence found" instead of scanning a table of zeros.
        self._empty_state = EmptyState(
            "No IOC Evidence",
            "No indicators of compromise were extracted from this "
            "report.",
        )

        self._empty_state.setVisible(False)

        self._table = QTableWidget()
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._table.setColumnCount(4)

        self._table.setHorizontalHeaderLabels(
            [
                "IOC Type",
                "Count",
                "Risk Significance",
                "Threat Intelligence",
            ]
        )

        self._table.verticalHeader().setVisible(
            False,
        )

        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )

        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )

        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )

        self._table.horizontalHeader().setStretchLastSection(
            True,
        )

        self._table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        self._build_ui()

        self._table.cellClicked.connect(
            self._row_clicked,
        )

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addWidget(
            self._table,
            1,
        )

        layout.addWidget(
            self._empty_state,
            1,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
        threat_intel_overview: dict | None = None,
    ) -> None:
        """
        Display IOC information for an investigation.

        Args:
            investigation:
                The investigation to display.
            threat_intel_overview:
                Optional result of
                `build_investigation_threat_intel_overview()`. When
                provided, its `short_label` drives the Threat
                Intelligence column for every enrichable row (SHA256,
                IPv4, domains, URLs -- e.g. "Enriched (3/5)", "No
                API Key Configured") so the analyst can see
                enrichment coverage without opening a single IOC.
                When omitted, those rows show a plain "unknown"
                placeholder rather than a fabricated value -- any
                other IOC category always shows "Not Supported",
                since the current provider integration does not
                enrich it at all, regardless of this argument.
        """

        self._ioc_data = investigation.iocs

        self._threat_intel_overview = threat_intel_overview

        total_iocs = sum(
            len(values) for values in self._ioc_data.values()
        )

        self._table.setVisible(total_iocs > 0)

        self._empty_state.setVisible(total_iocs == 0)

        if total_iocs > 0:

            self._populate_table()

    def _populate_table(self) -> None:
        """
        Fill the table from `self._ioc_data`.
        """

        self._table.setRowCount(
            len(self.IOC_TITLES),
        )

        for row, (key, title) in enumerate(
            self.IOC_TITLES.items()
        ):
            values = self._ioc_data.get(
                key,
                [],
            )

            self._table.setItem(
                row,
                self._COLUMN_TYPE,
                QTableWidgetItem(
                    title,
                ),
            )

            self._table.setItem(
                row,
                self._COLUMN_COUNT,
                QTableWidgetItem(
                    str(len(values)),
                ),
            )

            self._table.setCellWidget(
                row,
                self._COLUMN_SIGNIFICANCE,
                self._make_significance_cell(key),
            )

            self._table.setItem(
                row,
                self._COLUMN_THREAT_INTEL,
                QTableWidgetItem(
                    self._threat_intel_label(key),
                ),
            )

        self._table.resizeColumnsToContents()

        self._table.resizeRowsToContents()

        self._table.updateGeometry()

        self.updateGeometry()

    def _make_significance_cell(self, ioc_type: str) -> QWidget:
        """
        Build the centered risk-significance badge for one row.

        Reuses the shared `StatusBadge` widget and the centralized
        `severity_to_badge_type` mapping (already used for severity
        and for per-IOC significance in `IOCDetailDialog`) so this
        table gains the same color coding without introducing a
        second styling scheme.
        """

        significance = ioc_type_significance(ioc_type)

        cell = QWidget()

        cell_layout = QHBoxLayout(cell)

        cell_layout.setContentsMargins(
            Spacing.XS, Spacing.XXS, Spacing.XS, Spacing.XXS
        )

        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cell_layout.addWidget(
            StatusBadge(
                significance.upper(),
                badge_type=severity_to_badge_type(significance),
            )
        )

        return cell

    def _threat_intel_label(self, ioc_type: str) -> str:
        """
        Return the Threat Intelligence column text for one row.

        Never fabricates a coverage figure: SHA256 shows the real
        `build_investigation_threat_intel_overview()` result when
        one was supplied, or an explicit "unknown" placeholder when
        it wasn't. Every other category honestly reports that the
        current provider integration does not enrich it at all.
        """

        if ioc_type not in _ENRICHABLE_IOC_TYPES:
            return _TI_NOT_SUPPORTED_LABEL

        if self._threat_intel_overview is None:
            return _TI_UNKNOWN_LABEL

        return self._threat_intel_overview["short_label"]

    def _row_clicked(
        self,
        row: int,
        column: int,
    ) -> None:
        """
        Handle IOC table row selection.
        """

        del column

        keys = list(
            self.IOC_TITLES.keys()
        )

        if row >= len(keys):
            return

        key = keys[row]

        values = self._ioc_data.get(
            key,
            [],
        )

        self.ioc_selected.emit(
            key,
            values,
        )

    def select_category(self, ioc_type: str) -> bool:
        """
        Select and display the given IOC category, as if the
        analyst had clicked its row directly.

        Used by the risk explanation's "Risk explanation ->
        Contributing IOC -> IOC context" drill-down (see
        PHASE3C-2 section 5), so that navigating in from the risk
        explanation goes through the same selection path a manual
        click would, rather than a second, parallel one.

        Returns:
            True if `ioc_type` is a known category and was
            selected; False otherwise (this should not normally
            happen, since callers pass a type read from this same
            investigation's own data).
        """

        keys = list(
            self.IOC_TITLES.keys()
        )

        if ioc_type not in keys:
            return False

        row = keys.index(ioc_type)

        self._table.selectRow(row)

        self._row_clicked(row, self._COLUMN_TYPE)

        return True

    def reset(self) -> None:
        """
        Reset the widget.
        """

        self._ioc_data.clear()

        self._threat_intel_overview = None

        self._table.setRowCount(
            0,
        )

        self._table.setVisible(True)

        self._empty_state.setVisible(False)