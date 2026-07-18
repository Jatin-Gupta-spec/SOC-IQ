"""
Dashboard page for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.widgets.page_container import PageContainer
from app.gui.widgets.summary_card import SummaryCard


class DashboardPage(QWidget):
    """
    Dashboard page displayed when the application starts.
    """

    def __init__(self) -> None:
        super().__init__()

        self._controller = DashboardController()

        self._container = PageContainer(
            title="Dashboard",
            description=(
                "Overview of investigations, IOC analysis, "
                "risk assessment, and system status."
            ),
        )

        self._reports_card = SummaryCard(
            title="Reports",
            subtitle="Analyzed Reports",
            footer="Ready",
        )

        self._ioc_card = SummaryCard(
            title="IOCs",
            subtitle="Indicators Extracted",
            footer="Ready",
        )

        self._risk_card = SummaryCard(
            title="High Risk",
            subtitle="Critical Investigations",
            footer="No Active Alerts",
        )

        self._database_card = SummaryCard(
            title="Database",
            subtitle="SQLite Repository",
            footer="Operational",
        )

        self._build_ui()

        self._load_dashboard()

    def _build_ui(self) -> None:
        """
        Build the dashboard user interface.
        """

        layout = self._container.content_layout()

        statistics_layout = QGridLayout()

        statistics_layout.setHorizontalSpacing(16)
        statistics_layout.setVerticalSpacing(16)

        statistics_layout.addWidget(
            self._reports_card,
            0,
            0,
        )

        statistics_layout.addWidget(
            self._ioc_card,
            0,
            1,
        )

        statistics_layout.addWidget(
            self._risk_card,
            1,
            0,
        )

        statistics_layout.addWidget(
            self._database_card,
            1,
            1,
        )

        layout.addLayout(
            statistics_layout,
        )

        self._recent_activity = QLabel()

        self._recent_activity.setObjectName(
            "dashboardEmptyState"
        )

        layout.addWidget(
            self._recent_activity,
        )

        root_layout = QVBoxLayout()

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root_layout.addWidget(
            self._container,
        )

        self.setLayout(
            root_layout,
        )

    def _load_dashboard(self) -> None:
        """
        Load dashboard information from the controller.
        """

        summary = self._controller.get_summary()

        self._reports_card.update_card(
            value=summary["reports"],
        )

        self._ioc_card.update_card(
            value=summary["iocs"],
        )

        self._risk_card.update_card(
            value=summary["high_risk"],
        )

        self._database_card.update_card(
            value=summary["database"],
        )

        reports = int(summary["reports"])

        if reports == 0:
            self._recent_activity.setText(
                "Recent Activity\n\n"
                "No investigations available.\n"
                "Analyze a report to begin."
            )
        else:
            self._recent_activity.setText(
                "Recent Activity\n\n"
                f"{reports} investigation(s) available.\n"
                "Open the Investigation History page "
                "to review completed analyses."
            )