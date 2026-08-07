"""
Application-wide event bus for the SOC-IQ desktop application.

This module provides a centralized event dispatcher that enables
communication between independent GUI components without creating
direct dependencies between them.

Scope: this bus carries settings changes, per-page refresh
requests, and generic status/error messages. Investigation
lifecycle events (selected/created/updated/removed) live on
the separate `app.gui.events.event_bus.event_bus` singleton
instead -- see that module's docstring. In particular,
`investigation_deleted` here and `investigation_removed` on
`event_bus` are NOT the same signal and are not bridged to one
another; deleting an investigation should emit
`event_bus.investigation_removed` so pages that already
subscribe to it (e.g. `IOCViewerPage`) refresh correctly.
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