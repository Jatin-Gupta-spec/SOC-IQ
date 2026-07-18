"""
Workspace controller for the SOC-IQ desktop application.

Coordinates loading investigation data for the
Investigation Workspace.
"""

from __future__ import annotations

from app.database.models import Investigation
from app.database.service import InvestigationService


class WorkspaceController:
    """
    Controller responsible for loading investigations
    into the Investigation Workspace.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
    ) -> None:

        self._service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )

    def load_investigation(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Load a single investigation.
        """

        return self._service.get_by_id(
            investigation_id
        )