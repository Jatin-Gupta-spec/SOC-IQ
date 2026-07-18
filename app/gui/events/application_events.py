"""
Application-wide event bus for the SOC-IQ desktop application.

This module provides a centralized event dispatcher that enables
communication between independent GUI components without creating
direct dependencies between them.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class ApplicationEvents(QObject):
    """
    Global application event dispatcher.

    All major GUI components communicate through this object
    instead of referencing one another directly.
    """

    investigation_created = Signal(dict)

    investigation_deleted = Signal(int)

    investigation_updated = Signal(dict)

    dashboard_refresh_requested = Signal()

    history_refresh_requested = Signal()

    ioc_refresh_requested = Signal()

    threat_intelligence_refresh_requested = Signal()

    risk_dashboard_refresh_requested = Signal()

    settings_changed = Signal(dict)

    status_message = Signal(str)

    error_occurred = Signal(str)


events = ApplicationEvents()