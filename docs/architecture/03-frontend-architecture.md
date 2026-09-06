# React + TypeScript Frontend Architecture

**Status:** Documentation Foundation (Phase 4A). No frontend code exists yet.
**Related:** Master Plan §9 (component/feature structure), §12 (information architecture,
see `13-frontend-information-architecture.md`), §13 (workspace, see
`14-investigation-workspace-architecture.md`), ADR-002.

## CURRENT STATE

No React/TypeScript code exists in this project. The current presentation layer is
PySide6 (`app/gui/**`, CONFIRMED, Master Plan §1.1/§1.3). The existing GUI's controller and
service layer (`app/gui/controllers/*`, `app/gui/services/*`) already separates
"what action to take" from "how to render it" to some degree, which is the closest current
analog to a future React feature module's data-fetching logic — but the rendering code itself
(`app/gui/pages/*`, `app/gui/widgets/*`) has no target-architecture equivalent beyond the
*concepts* it renders (see Master Plan §27 Preserve/Adapt/Redesign/Remove matrix: GUI pages
and widgets are classified REMOVE, with their rendered concepts REDESIGNED as React
components).

## TARGET STATE (PROPOSED)

```
src/
├── app/                 shell, routing, providers
├── features/
│   ├── dashboard/
│   ├── analyze/
│   ├── investigation-workspace/
│   ├── ioc-explorer/
│   ├── threat-intel/
│   ├── risk/
│   ├── history/
│   ├── reports/
│   └── settings/
├── shared/
│   ├── components/       design-system components (see 11-design-system-architecture.md)
│   ├── api/                typed IPC client, generated from docs/contracts/ schemas
│   ├── events/              SSE/WS subscription hook (see 06-event-architecture.md)
│   ├── view-models/          map backend DTOs to presentation-ready shapes
│   └── state/                client session/UI state only (see 07-state-architecture.md)
└── styles/                  design tokens
```

**Responsibility boundary (hard rule, ADR-002 and Master Plan §2 diagram):** React owns UI,
view models, motion, and client-side session state. It never touches SQLite directly, never
implements risk scoring or threat-intel logic, and never duplicates Python domain logic. This
boundary is enforced structurally by the IPC contract (`docs/contracts/`) being the only way
the frontend can reach data — there is no code path for a "shortcut" query.

Async workflow pattern: a user action issues a command → the UI shows an optimistic "pending"
local state → the event stream confirms (`analysis.completed`) or corrects
(`analysis.failed`) the pending state → the relevant view model updates. There is no polling;
the event stream (`06-event-architecture.md`) is the sole source of truth for any
long-running operation's outcome.

## MIGRATION NOTES

Frontend build does not begin until Phase 4F (Master Plan §26), and only after the IPC
contract (Phase 4D) and Tauri foundation (Phase 4E) exist. The PySide6 GUI remains the only
working GUI client until the React frontend reaches feature parity (Phase 4O) — see ADR-009.

## UNKNOWN / REQUIRES VERIFICATION

Whether any currently-untraced GUI widget encodes logic (not just rendering) that must be
captured before that widget is retired — part of the same Phase 4B inventory referenced in
`02-python-backend-architecture.md`. **UNKNOWN — VERIFY IN PHASE 4B.**
