"""
History viewer for SOC-IQ investigations.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from app.database.models import Investigation
from app.database.service import InvestigationService
from app.logger import logger

console = Console()


class InvestigationHistory:
    """
    Provides history viewing functionality
    for stored investigations.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
    ) -> None:
        """
        Initialize the history viewer.
        """

        self._service = (
            service
            if service is not None
            else InvestigationService()
        )

        logger.debug(
            "InvestigationHistory initialized."
        )

    def list_all(
        self,
    ) -> list[Investigation]:
        """
        Return every stored investigation.
        """

        logger.info(
            "Loading investigation history."
        )

        return self._service.list_all()

    def get_by_id(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Return a single investigation.
        """

        logger.info(
            "Loading investigation %d",
            investigation_id,
        )

        return self._service.get_by_id(
            investigation_id,
        )

    def print_summary(
        self,
    ) -> None:
        """
        Display a summary table containing
        every investigation.
        """

        investigations = self.list_all()

        table = Table(
            title="Investigation History"
        )

        table.add_column(
            "ID",
            justify="right",
        )

        table.add_column(
            "Report",
        )

        table.add_column(
            "Risk",
            justify="center",
        )

        table.add_column(
            "Severity",
            justify="center",
        )

        table.add_column(
            "Status",
            justify="center",
        )

        if not investigations:

            console.print(
                "[yellow]No investigations found.[/yellow]"
            )

            return

        for investigation in investigations:

            table.add_row(
                str(
                    investigation.investigation_id
                ),
                investigation.report_name,
                str(
                    investigation.risk_score
                ),
                investigation.severity,
                investigation.status,
            )

        console.print(
            table,
        )

    def print_details(
        self,
        investigation_id: int,
    ) -> None:
        """
        Display detailed information about
        a single investigation.
        """

        investigation = self.get_by_id(
            investigation_id,
        )

        if investigation is None:

            console.print(
                "[red]Investigation not found.[/red]"
            )

            return

        table = Table(
            title=(
                f"Investigation "
                f"#{investigation_id}"
            )
        )

        table.add_column(
            "Field",
            style="cyan",
        )

        table.add_column(
            "Value",
        )

        table.add_row(
            "Report",
            investigation.report_name,
        )

        table.add_row(
            "Risk Score",
            str(
                investigation.risk_score
            ),
        )

        table.add_row(
            "Severity",
            investigation.severity,
        )

        table.add_row(
            "Status",
            investigation.status,
        )

        table.add_row(
            "Analyzed At",
            investigation.analyzed_at.isoformat(),
        )

        table.add_row(
            "IOC Types",
            str(
                len(
                    investigation.iocs
                )
            ),
        )

        table.add_row(
            "Threat Intelligence",
            (
                "Available"
                if investigation.threat_intelligence
                else "None"
            ),
        )

        console.print(
            table,
        )