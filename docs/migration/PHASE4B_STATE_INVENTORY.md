# Phase 4B — State Inventory

**Status:** Phase 4B (Source-Verified). Resolves the `07-state-architecture.md` UNKNOWN:
"Current `ApplicationState` responsibilities and its relationship (if any) to the two Qt
event buses."

**Source read in full:** `app/gui/events/application_state.py` (231 lines) and its
consumers (traced via grep, not all individually opened).

## What `ApplicationState` actually is

A class-level (not instance-level) singleton-by-construction: all state lives on class
attributes (`_current_investigation`, `_selected_ioc`) guarded by a single class-level
`threading.RLock`. All access goes through classmethods — no public attribute access exists.

## SERVER STATE (data that originates from SQLite via the domain/application layer)

| Field | Type | Access pattern | Notes |
|---|---|---|---|
| `_current_investigation` | `Investigation \| None` | `set_current_investigation()` (silent), `select_investigation()` (emits `event_bus.investigation_selected`), `get_current_investigation()`, `clear_current_investigation()` (emits) | **Deep-copied on every set and every get.** This is a deliberate defensive-copy pattern (documented inline) specifically because `Investigation.iocs` and `.threat_intelligence` are mutable dict/list fields — a shallow copy would let one page's local mutation silently corrupt what every other page reads. |

This is the entire server-state surface. Everything else in this class is UI-navigation
state.

## UI STATE (transient, GUI-navigation-only, must never be persisted)

| Field | Type | Access pattern | Notes |
|---|---|---|---|
| `_selected_ioc` | `SelectedIOC \| None` (frozen dataclass: `ioc_type: str`, `value: str`) | `set_selected_ioc()`, `get_selected_ioc()`, `clear_selected_ioc()` | Explicitly documented as "must never be persisted" (PHASE2_PART2A scope reference in the source docstring). Automatically cleared whenever a new investigation is selected (`select_investigation()` resets it), since a selected IOC only makes sense in the context of the investigation it was selected from. |

No other UI-only fields (selected page, active workspace tab, modal visibility, filters,
form state) were found inside `ApplicationState` itself. Per the class's own docstring scope
("Stores the currently active investigation so that all GUI pages can access the same
investigation"), this class is deliberately narrow — it is not a general-purpose UI state
store. Other UI state (if it exists) must live elsewhere, e.g. directly on individual page/
widget instances; this was not traced further, as the responsible files
(`app/gui/pages/*`, `app/gui/widgets/*`) are outside Phase 4B's stated scope
(`app/services/`, `app/gui/controllers/`, `app/gui/services/`).

## Relationship to the event buses

`ApplicationState` imports and emits directly on `app.gui.events.event_bus.event_bus` (not
`application_events.events`) — specifically `investigation_selected`, on both
`select_investigation()` and `clear_current_investigation()` (the latter deliberately reuses
`investigation_selected` rather than adding a new signal, per an explicit inline comment,
since every existing subscriber already handles a `None` current investigation).

`ApplicationState` has **no relationship at all** to `application_events.events` — it never
imports it, and no `events.*` signal is emitted from this file. This confirms the 4A
documentation's UNKNOWN with a direct answer: `ApplicationState` is coupled to exactly one
of the two buses, not both, and not neither.

## Locking discipline (relevant for future thread-safety carryover)

Every mutation is documented as intentionally emitting its `event_bus` signal **outside**
the lock, specifically to avoid deadlock if a connected slot re-enters `ApplicationState`
synchronously (e.g. via a Qt `DirectConnection` from another thread). This is a correctness-
relevant detail: a naive refactor that "cleans up" by moving the emit inside the `with
cls._lock:` block would reintroduce a real deadlock risk, given `AnalysisWorker` runs on a
background `QThread` and writes that could plausibly flow through this state object in the
future.

## Target ownership (per `07-state-architecture.md`'s already-proposed table, now confirmed
consistent with actual source)

- `_current_investigation` → SERVER STATE → target owner: Python domain + SQLite, fetched by
  React via query, not pushed through this class's replacement.
- `_selected_ioc` → UI STATE → target owner: React client state store (session-only, never
  persisted) — this is exactly the worked example already given in
  `07-state-architecture.md` ("the selected-IOC id inside the Investigation Workspace... is
  discarded on app restart").

No correction to `07-state-architecture.md`'s TARGET STATE table is required; only its
CURRENT STATE section's explicit UNKNOWN is resolved by this document.
