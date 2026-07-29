"""
Dashboard page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.events.event_bus import event_bus
from app.gui.events.application_state import (
    ApplicationState,
)
from app.gui.widgets.dashboard.kpi_section import (
    KPISection,
)
from app.gui.widgets.recent_investigations_widget import (
    RecentInvestigationsWidget,
)
from app.gui.components.buttons.animated_button import (
    AnimatedButton,
)

from app.gui.components.layout.page_header import (
    PageHeader,
)
from datetime import datetime
from app.gui.widgets.panel import Panel


class DashboardPage(QWidget):
    """
    Dashboard page displayed when the application starts.
    """

    def __init__(self) -> None:
        super().__init__()

        self._controller = DashboardController()

        self._header_widget = PageHeader(
            title="Dashboard",
            subtitle=(
                "Overview of investigations, IOC analysis, "
                "risk assessment, and system status."
            ),
        )

        self._header_widget.add_action(
            AnimatedButton("Refresh")
        )

        self._header_widget.add_action(
            AnimatedButton("Export")
        )

        self._kpi_section = KPISection()

        self._recent_table = (
            RecentInvestigationsWidget()
        )

        self._build_ui()

        # NEW: Refresh whenever the selected investigation changes.
        event_bus.investigation_selected.connect(
            self.refresh,
        )

        self._recent_table.investigation_selected.connect(
            self._open_investigation,
        )

        self._recent_table.export_requested.connect(
            self._export_investigation,
        )

        self._recent_table.delete_requested.connect(
            self._delete_investigation,
        )

        self._load_dashboard()

    def _build_ui(self) -> None:
        """
        Build the dashboard user interface.
        """

        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        root_layout.setSpacing(24)

        layout = root_layout

        layout.addWidget(
            self._header_widget,
        )

        layout.addWidget(
            self._kpi_section,
        )

        self._recent_activity = QLabel()

        self._recent_activity.setObjectName(
            "dashboardEmptyState"
        )

        self._recent_activity.setWordWrap(
            True,
        )

        overview_panel = Panel()

        overview_layout = QVBoxLayout(
            overview_panel,
        )

        overview_layout.addWidget(
            QLabel(
                "Investigation Overview",
            )
        )

        overview_layout.addWidget(
            self._recent_activity,
        )

        layout.addWidget(
            overview_panel,
        )

        recent_panel = Panel()

        recent_layout = QVBoxLayout(
            recent_panel,
        )

        recent_layout.addWidget(
            QLabel(
                "Recent Investigations",
            )
        )

        recent_layout.addWidget(
            self._recent_table,
        )

        layout.addWidget(
            recent_panel,
        )

        status_panel = Panel()

        status_layout = QVBoxLayout(
            status_panel,
        )

        status_layout.addWidget(
            QLabel(
                "System Status",
            )
        )

        self._status_placeholder = QLabel(
            "All SOC-IQ services are operational."
        )

        self._status_placeholder.setObjectName(
            "dashboardEmptyState",
        )

        status_layout.addWidget(
            self._status_placeholder,
        )

        layout.addWidget(
            status_panel,
        )

        layout.addStretch()


    def refresh(self) -> None:
        """
        Refresh the dashboard with the latest
        application data.
        """

        self._load_dashboard()

    def _open_investigation(
        self,
        investigation,
    ) -> None:
        """
        Open an investigation selected from
        the recent investigations table.
        """

        ApplicationState.select_investigation(
            investigation,
        )

    def _export_investigation(
        self,
        investigation,
    ) -> None:
        """
        Handle export request.
        """

        print(
            "Export:",
            investigation.report_name,
        )


    def _delete_investigation(
        self,
        investigation,
    ) -> None:
        """
        Handle delete request.
        """

        print(
            "Delete:",
            investigation.report_name,
        )

    def _load_dashboard(self) -> None:
        """
        Load dashboard information from the controller.
        """

        summary = self._controller.get_summary()

        self._header_widget.set_last_refresh(
            datetime.now().strftime(
                "%d %b %Y %H:%M:%S",
            ),
        )

        self._header_widget.set_status(
            "Database",
            summary["database"],
        )

        self._kpi_section.set_metrics(
            reports=str(summary["reports"]),
            iocs=str(summary["iocs"]),
            high_risk=str(summary["high_risk"]),
            database=str(summary["database"]),
        )

        recent = (
            self._controller.get_recent_investigations()
        )

        self._recent_table.load_investigations(
            recent,
        )

        latest = (
            self._controller.get_latest_investigation()
        )

        if latest is None:

            self._recent_activity.setText(
                "Recent Activity\n\n"
                "No investigations available.\n"
                "Analyze a report to begin."
            )

            return

        analyzed_at = (
            latest.analyzed_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        self._recent_activity.setText(
            "Recent Activity\n\n"
            "Latest Investigation\n\n"
            f"Report Name : {latest.report_name}\n"
            f"Analyzed    : {analyzed_at}\n"
            f"Risk Score  : {latest.risk_score}\n"
            f"Severity    : {latest.severity}"
        )