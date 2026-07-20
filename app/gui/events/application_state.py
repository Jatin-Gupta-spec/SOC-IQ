"""
Shared application state for the SOC-IQ desktop application.

Stores the currently active investigation so that all GUI pages
can access the same investigation without directly depending on
each other.
"""

from __future__ import annotations

from app.database.models import Investigation


class ApplicationState:
    """
    Shared application state.
    """

    current_investigation: Investigation | None = None

    @classmethod
    def set_current_investigation(
        cls,
        investigation: Investigation | None,
    ) -> None:
        """
        Store the active investigation.
        """

        cls.current_investigation = investigation

    @classmethod
    def get_current_investigation(
        cls,
    ) -> Investigation | None:
        """
        Return the active investigation.
        """

        return cls.current_investigation

    @classmethod
    def clear_current_investigation(
        cls,
    ) -> None:
        """
        Clear the active investigation.
        """

        cls.current_investigation = None

    @classmethod
    def has_investigation(
        cls,
    ) -> bool:
        """
        Return whether an investigation is loaded.
        """

        return cls.current_investigation is not None