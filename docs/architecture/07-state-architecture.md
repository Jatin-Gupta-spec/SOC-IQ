# Client-Side State Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §3 (data/command/event/state ownership model), §9 (frontend state
folder), §13 (workspace state persistence across tabs).

## CURRENT STATE

The current GUI has an `ApplicationState`-adjacent concept referenced in the prior
(pre-Phase-4) audit baseline, alongside the two event buses described in
`06-event-architecture.md`. Its exact current responsibilities were not independently
re-verified at the source level as part of this documentation pass and are treated as
**UNKNOWN — VERIFY IN PHASE 4B** pending a direct read.

## TARGET STATE (PROPOSED)

Ownership split (Master Plan §3):

| Category | Owner | Persisted where |
|---|---|---|
| Data (investigations, IOCs, TI results, risk scores, reports, settings) | Python domain + SQLite | Server-side, durable |
| Commands | Python application boundary | N/A (imperative, not stored) |
| Events | Python publishes; Tauri relays; React subscribes | N/A (transient, replayed only via re-query) |
| State (current page, selected investigation/IOC, active analysis, UI-only flags) | React client state store | In-memory only, per session |

The frontend state store (e.g. Zustand or an equivalent lightweight store, chosen at
implementation time, not fixed by this document) holds **only** UI/session state — it is never
the source of truth for domain data, and it is explicitly never persisted to browser storage
between sessions; the server (SQLite) is the only durable store, consistent with the frontend
having no direct filesystem/network access.

A concrete example of the boundary in practice: the selected-IOC id inside the Investigation
Workspace (`14-investigation-workspace-architecture.md`) lives in this store and survives tab
switches within a session, but is discarded on app restart — re-selecting on restart means
re-issuing a command, not reading persisted UI state.

## MIGRATION NOTES

State-store implementation is part of Phase 4F/4G (design system and application shell) —
no state management library is selected as final in this documentation pass.

## PHASE 4B VERIFICATION (source-verified; supersedes the UNKNOWN section below)

**BEFORE:** "Its exact current responsibilities were not independently re-verified at the
source level... UNKNOWN — VERIFY IN PHASE 4B."

**AFTER:** Full read of `app/gui/events/application_state.py` (231 lines) confirms
`ApplicationState` is a narrow, class-level singleton holding exactly two fields: one SERVER
STATE field (`_current_investigation`, deep-copied on every read/write to prevent shared-
mutation bugs) and one UI STATE field (`_selected_ioc`, explicitly documented as
never-persisted, auto-cleared whenever a new investigation is selected). It is coupled to
exactly **one** of the two event buses — `event_bus` (not `application_events.events`) —
emitting `investigation_selected` on both `select_investigation()` and
`clear_current_investigation()`. This confirms the TARGET STATE table below requires no
changes; the existing SERVER STATE / UI STATE ownership split already matches what was
found in source.

**REASON:** Phase 4B §12 (State Inventory, mandatory).

**SOURCE EVIDENCE:** `app/gui/events/application_state.py` (full read). Full detail:
`docs/migration/PHASE4B_STATE_INVENTORY.md`.

## UNKNOWN / REQUIRES VERIFICATION (historical — resolved above)

Current `ApplicationState` responsibilities and its relationship (if any) to the two Qt event
buses: ~~UNKNOWN — VERIFY IN PHASE 4B~~ **RESOLVED — see PHASE 4B VERIFICATION above.**
