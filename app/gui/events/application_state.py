"""
Shared application state for the SOC-IQ desktop application.
"""

from __future__ import annotations

from app.database.models import Investigation


class ApplicationState:
    """
    Stores the currently selected investigation.

    This acts as a lightweight shared state between
    GUI pages and controllers.
    """

    current_investigation: Investigation | None = None