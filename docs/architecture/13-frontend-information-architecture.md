# Frontend Information Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §12.

## CURRENT STATE

The current PySide6 GUI has a sidebar and page-based navigation (CONFIRMED,
`app/gui/widgets/sidebar.py`, `app/gui/pages/*.py`: dashboard, analyze, history, investigation
workspace, IOC viewer, risk dashboard, settings, threat intel — eight page modules present).
The exact current navigation hierarchy and interaction model (breadcrumbs, contextual
actions, search) were not independently re-verified in full during this pass and should be
treated as **UNKNOWN — VERIFY IN PHASE 4B** where not explicitly confirmed above.

## TARGET STATE (PROPOSED)

- **Primary navigation** (persistent sidebar): Dashboard · Analyze · Investigations · IOC
  Explorer · Threat Intel · Risk · Reports · Settings — a direct target-architecture mapping
  of the eight current page modules onto eight primary nav destinations.
- **Investigation-centric secondary navigation:** once inside an investigation, the workspace
  tabs (see `14-investigation-workspace-architecture.md`) replace the need to navigate away
  and back to the top-level nav.
- **Global search / command palette** (`Cmd/Ctrl+K`): jump to any investigation, IOC, or
  action (e.g. "export current investigation as PDF") without losing context.
- **Dashboard layout constraint:** the dashboard targets 1440×900 without vertical scrolling,
  via a fixed 12-column grid (KPI row + queue + IOC distribution + timeline as defined panel
  sizes, not stacked cards that grow unbounded). At 1280×720, the same grid collapses the
  timeline panel into a secondary tab rather than introducing page-level scroll — layout
  problems are solved by re-composing the grid, not by adding scroll.

## MIGRATION NOTES

Navigation shell is Phase 4G (Master Plan §26), built against a mock-data version of the
above structure before real dashboard data is wired in Phase 4H.

## UNKNOWN / REQUIRES VERIFICATION

Exact current sidebar/navigation interaction details beyond the page-module list above:
**UNKNOWN — VERIFY IN PHASE 4B.**
