"""
Application-wide event bus.

Provides signals that allow GUI components to communicate
without directly depending on one another.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """
    Central application event bus.
    """

    investigation_selected = Signal()

    investigation_created = Signal()

    investigation_updated = Signal()

    investigation_removed = Signal()

    application_state_changed = Signal()


event_bus = EventBus()