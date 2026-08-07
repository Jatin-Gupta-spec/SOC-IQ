"""
Application-wide event bus.

Provides signals that allow GUI components to communicate
without directly depending on one another.

Scope: this bus is for the *investigation lifecycle* --
selection, creation, update, and removal of an
`Investigation` record, plus the generic
`application_state_changed` signal. A second, separate
singleton (`app.gui.events.application_events.events`)
carries a different set of concerns (settings changes,
per-page refresh requests, status/error messages). The two
are NOT interchangeable: a page that deletes an investigation
must emit `investigation_removed` here, not
`events.investigation_deleted` on the other bus, or
subscribers on this bus (e.g. `IOCViewerPage`) will silently
miss the update. If a new cross-cutting event doesn't clearly
belong to the investigation lifecycle, prefer adding it to
`application_events.py` instead of introducing a third bus.
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