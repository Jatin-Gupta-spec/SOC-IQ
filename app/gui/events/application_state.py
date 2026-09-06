"""
Shared application state for the SOC-IQ desktop application.

Stores the currently active investigation so that all GUI pages
can access the same investigation without directly depending on
each other.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass

from app.database.models import Investigation
from app.gui.events.event_bus import event_bus


@dataclass(frozen=True, slots=True)
class SelectedIOC:
    """
    Identifies a single IOC value currently under investigation
    by the analyst, within the context of the current investigation.

    `ioc_type` is the raw IOC category key used throughout the
    codebase (e.g. "sha256", "ipv4"), not a display title.
    """

    ioc_type: str

    value: str


class ApplicationState:
    """
    Shared application state.

    Access to the current investigation is synchronized with a
    reentrant lock. This is a global, class-level, mutable
    value that may be read or written from more than one
    thread over the application's lifetime (e.g. background
    analysis work), so plain unsynchronized attribute access
    is not safe to rely on long-term.

    The stored value is private (`_current_investigation`) so
    that all reads and writes are forced through the
    classmethods below, which hold the lock and, where
    relevant, notify the rest of the app via `event_bus`.
    Direct attribute access (`ApplicationState.current_investigation
    = ...`) would silently bypass both.
    """

    _lock = threading.RLock()

    _current_investigation: Investigation | None = None

    # The specific IOC value the analyst is currently drilled into
    # within the current investigation (e.g. one selected SHA256
    # hash), if any. This is deliberately a *separate* field from
    # `_current_investigation` rather than folded into it: it is
    # transient GUI-navigation state, not investigation data, and
    # must never be persisted (see PHASE2_PART2A scope: "Do not
    # persist transient GUI state unnecessarily").
    _selected_ioc: SelectedIOC | None = None

    @classmethod
    def set_current_investigation(
        cls,
        investigation: Investigation | None,
    ) -> None:
        """
        Store the active investigation.
        """

        with cls._lock:
            # Store a defensive copy rather than the caller's
            # reference. Without this, the caller could keep
            # mutating the object it just handed us (e.g.
            # `inv.status = "x"`) and silently corrupt shared
            # state that other pages read from, with no lock
            # held and no event emitted for that change.
            #
            # This must be a deep copy, not a shallow one:
            # `Investigation.iocs` and `.threat_intelligence` are
            # themselves mutable containers (dict/list). A shallow
            # `copy.copy()` only duplicates the top-level dataclass
            # instance -- the nested dict/list objects are still
            # shared with the caller's original, so e.g.
            # `inv.iocs["SHA256"].append(...)` on the caller's
            # reference would still corrupt what's stored here.
            cls._current_investigation = (
                copy.deepcopy(investigation) if investigation is not None else None
            )

    @classmethod
    def select_investigation(
        cls,
        investigation: Investigation,
    ) -> None:
        """
        Store the active investigation and notify
        the application that it has changed.
        """

        with cls._lock:
            # See the comment in `set_current_investigation` --
            # this must be a deep copy so nested `iocs` /
            # `threat_intelligence` containers aren't shared with
            # the caller's reference.
            cls._current_investigation = copy.deepcopy(investigation)

            # A previously selected IOC belongs to whichever
            # investigation was loaded when it was selected. Carrying
            # it over to a newly selected investigation would let the
            # IOC detail view silently show a value that isn't part
            # of the investigation currently on screen.
            cls._selected_ioc = None

        # Emitted outside the lock: a slot connected to this
        # signal could call back into ApplicationState (e.g.
        # from a DirectConnection on another thread), and
        # holding the lock across the emit would risk a
        # deadlock in that case.
        event_bus.investigation_selected.emit()

    @classmethod
    def get_current_investigation(
        cls,
    ) -> Investigation | None:
        """
        Return the active investigation.

        Returns a defensive deep copy, not the stored instance,
        so that a caller mutating the object it gets back (e.g.
        appending to `investigation.iocs["SHA256"]`, not just
        reassigning `investigation.status`) can't reach through
        and mutate the shared state itself out from under every
        other page holding a reference. A shallow copy would
        still share the nested `iocs`/`threat_intelligence`
        dict and list objects with the stored instance.
        """

        with cls._lock:
            if cls._current_investigation is None:
                return None

            return copy.deepcopy(cls._current_investigation)

    @classmethod
    def clear_current_investigation(
        cls,
    ) -> None:
        """
        Clear the active investigation and notify the
        application that it has changed.
        """

        with cls._lock:
            cls._current_investigation = None
            cls._selected_ioc = None

        # Previously this cleared the state but never told
        # anyone. Pages that only refresh on
        # `investigation_selected`/`investigation_updated`/
        # `investigation_removed` (see IOCViewerPage) would
        # keep showing the just-cleared investigation's data
        # indefinitely. `investigation_selected` is the
        # existing "current investigation changed" signal and
        # every subscriber already handles a `None` current
        # investigation correctly, so it's reused here rather
        # than introducing a new event_bus signal.
        event_bus.investigation_selected.emit()

    @classmethod
    def has_investigation(
        cls,
    ) -> bool:
        """
        Return whether an investigation is loaded.
        """

        with cls._lock:
            return cls._current_investigation is not None

    @classmethod
    def set_selected_ioc(
        cls,
        ioc_type: str,
        value: str,
    ) -> None:
        """
        Record which IOC value the analyst is currently drilled
        into, within the current investigation.

        This does not validate that `value` actually belongs to
        the current investigation -- callers (the IOC detail flow)
        already have that guarantee because the value came from
        the investigation's own extracted IOCs.
        """

        with cls._lock:
            cls._selected_ioc = SelectedIOC(
                ioc_type=ioc_type,
                value=value,
            )

    @classmethod
    def get_selected_ioc(
        cls,
    ) -> SelectedIOC | None:
        """
        Return the currently selected IOC, if any.

        `SelectedIOC` is frozen/immutable, so unlike
        `get_current_investigation()` no defensive copy is needed.
        """

        with cls._lock:
            return cls._selected_ioc

    @classmethod
    def clear_selected_ioc(
        cls,
    ) -> None:
        """
        Clear the currently selected IOC without affecting the
        current investigation.
        """

        with cls._lock:
            cls._selected_ioc = None