"""
History controller for the SOC-IQ desktop application.

This controller prepares investigation history data
for presentation in the GUI and delegates business
operations to the InvestigationService.
"""

from __future__ import annotations

import logging

from app.database.models import Investigation
from app.database.service import InvestigationService

logger = logging.getLogger(__name__)


class HistoryController:
    """
    Controller responsible for retrieving and
    managing investigation history.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
    ) -> None:
        """
        Initialize the history controller.
        """

        self._investigation_service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )

    def get_recent_investigations(
        self,
        limit: int = 10,
    ) -> list[Investigation]:
        """
        Return recent investigations.

        The ``limit`` argument is always explicitly passed to
        ``InvestigationService.find_recent`` — including this
        method's own default of ``10`` — so the result does not
        depend on any implicit/default behavior of the underlying
        repository. What ``find_recent`` does internally with that
        explicit limit (e.g. whether it can return fewer than
        requested, or how ordering is applied) is repository
        behavior that cannot be verified from this file alone.

        Raises
        ------
        Exception
            Propagated (after logging) if retrieval fails. A
            database failure must not be reported as an empty
            history.
        """

        try:
            return self._investigation_service.find_recent(
                limit,
            )
        except Exception:
            logger.exception(
                "Failed to load recent investigations (limit=%s)",
                limit,
            )
            raise

    def search_by_report_name(
        self,
        report_name: str,
    ) -> list[Investigation]:
        """
        Search investigations by report name.

        An empty/blank ``report_name`` is treated as "no search
        term" and short-circuits to an empty result rather than
        being sent to the repository, since it is unclear (and not
        verifiable from this file) whether the repository would
        interpret an empty string as a wildcard match against all
        investigations.

        Raises
        ------
        Exception
            Propagated (after logging) if the search fails.
        """

        if not report_name or not report_name.strip():
            return []

        try:
            return (
                self._investigation_service.find_by_report_name(
                    report_name,
                )
            )
        except Exception:
            logger.exception(
                "Failed to search investigations by report name '%s'",
                report_name,
            )
            raise

    def delete_investigation(
        self,
        investigation_id: int,
    ) -> bool:
        """
        Delete an investigation.

        Args:
            investigation_id:
                Database ID of the investigation.

        Returns:
            True if the investigation was deleted,
            otherwise False.

        Raises
        ------
        Exception
            Propagated (after logging) if the delete operation
            itself fails (e.g. a database error). This is distinct
            from the service legitimately returning ``False``
            because no matching investigation existed.
        """

        try:
            return self._investigation_service.delete(
                investigation_id,
            )
        except Exception:
            logger.exception(
                "Failed to delete investigation id=%s",
                investigation_id,
            )
            raise

    def get_investigation(
        self,
        investigation_id: int,
    ) -> Investigation | None:
        """
        Retrieve a single investigation by ID.

        Raises
        ------
        Exception
            Propagated (after logging) if retrieval fails. Only a
            genuine "no such investigation" result from the service
            should surface as ``None``.
        """

        try:
            return self._investigation_service.get_by_id(
                investigation_id,
            )
        except Exception:
            logger.exception(
                "Failed to load investigation id=%s",
                investigation_id,
            )
            raise

    def get_total_investigations(
        self,
    ) -> int:
        """
        Return the total number of investigations.

        Raises
        ------
        Exception
            Propagated (after logging) if the count query fails. A
            failure must not be reported as a count of ``0``.
        """

        try:
            return self._investigation_service.count()
        except Exception:
            logger.exception("Failed to count investigations")
            raise