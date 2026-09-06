# Event Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §15 (design), §1.3 (current-state defect), ADR-006, and
`docs/contracts/event-model.md`, `docs/contracts/event-versioning.md`,
`docs/contracts/correlation-ids.md`.

## CURRENT STATE (CONFIRMED — this is a documented existing defect, not a hypothetical one)

Two independent Qt signal buses exist simultaneously in `app/gui/events/`:

- `application_events.py` → the `events` singleton. Its own docstring states its scope
  (settings changes, per-page refresh requests, status/error messages) and includes a signal,
  `investigation_deleted`, that the same docstring flags as dead in practice.
- `event_bus.py` → the `event_bus` singleton. Its own docstring states its scope
  (investigation lifecycle: selected/created/updated/removed, plus
  `application_state_changed`).

Both files' docstrings explicitly warn engineers not to confuse `events.investigation_deleted`
with `event_bus.investigation_removed` — the project's own authors already diagnosed this
split as a live source of bugs and left a guard-rail comment rather than fixing it
(CONFIRMED by direct source read, Master Plan §1.3).

## TARGET STATE (PROPOSED)

**One** event system, published only by the Python backend, relayed unmodified by Tauri, and
consumed by React. Naming convention `domain.action` (`analysis.*`, `investigation.*`,
`ti.enrichment.*`) is chosen specifically to prevent the kind of naming collision the current
two-bus system has (two different names — `investigation_deleted` and
`investigation_removed` — for what should be one real-world event).

Every event carries an explicit `version` field from day one (see
`docs/contracts/event-versioning.md`), so payload evolution is never a silent breaking change
downstream. Example shape (Master Plan §15):

```json
{
  "event": "analysis.progress",
  "version": 1,
  "correlation_id": "an-8f3c...",
  "investigation_id": "inv-1029",
  "timestamp": "2026-08-20T10:15:32Z",
  "payload": { "stage": "ti_enrichment", "percent": 60 }
}
```

Canonical event catalog (representative, not exhaustive — full contract in
`docs/contracts/event-model.md`): `analysis.started`, `analysis.progress`,
`analysis.completed`, `analysis.failed`, `investigation.created`, `investigation.updated`,
`investigation.deleted`, `ti.enrichment.started`, `ti.enrichment.completed`,
`ti.enrichment.failed`.

## MIGRATION NOTES

Replacing the dual bus is explicitly **not** a rename-and-merge exercise (Master Plan §30.H,
"do not treat the two existing event buses as mergeable-by-renaming"). The unified model is
designed fresh in Phase 4D and the old Qt buses are retired only when `app/gui/**` is retired
in Phase 4O, once the React frontend has parity — until then, the two systems coexist as
separate concerns (Qt GUI on the old buses, new API layer on the new model) rather than being
bridged.

## PHASE 4B VERIFICATION (source-verified; supersedes the UNKNOWN section below)

**BEFORE:** "The same docstring flags `investigation_deleted` as dead in practice" (implying
one dead signal) / "Whether any test exercises the interaction between the two buses is
UNKNOWN — VERIFY IN PHASE 4B."

**AFTER:** A full emit/connect trace of all 16 signals across both buses (direct `grep` of
every `.emit(`/`.connect(` call site) found the dead-code problem is far larger than the
single signal previously flagged:
- Only **3 of 16 signals are genuinely live end-to-end**: `event_bus.investigation_selected`,
  `event_bus.investigation_created`, `events.settings_changed`.
- **2 signals are connected but never emitted**: `event_bus.investigation_updated`,
  `event_bus.investigation_removed` (both only connected in `ioc_viewer_page.py`, with no
  emit site anywhere — meaning an investigation being deleted currently notifies no
  subscriber on either bus, under either name).
- **10 of 11 signals on `application_events.events` are dead in both directions** (every
  signal except `settings_changed`), plus `event_bus.application_state_changed` is also dead
  in both directions on the other bus — 11 fully-dead signals total, not just the one
  previously documented.
- No test exercises the interaction between the two buses. **Confirmed absent**, resolving
  the prior UNKNOWN. This is itself flagged as a testing gap in
  `docs/migration/PHASE4B_TEST_COVERAGE_GAPS.md`.

**REASON:** Phase 4B §5 (Event Bus Investigation, mandatory).

**SOURCE EVIDENCE:** Full read of `app/gui/events/event_bus.py` (43 lines) and
`app/gui/events/application_events.py` (57 lines), plus exhaustive repository-wide grep of
every signal name's `.emit(`/`.connect(` usage. Full detail:
`docs/architecture/PHASE4B_ARCHITECTURAL_FINDINGS.md`.

## UNKNOWN / REQUIRES VERIFICATION (historical — resolved above)

Whether any existing test exercises the interaction between the two current Qt buses is
~~UNKNOWN — VERIFY IN PHASE 4B~~ **RESOLVED — no such test exists, see PHASE 4B
VERIFICATION above.** (Master Plan §1.8).
