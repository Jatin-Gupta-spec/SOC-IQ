# Event Model

**Status:** Documentation Foundation (Phase 4A). Architectural contract only.
**Related:** Master Plan §15, §16, `docs/architecture/06-event-architecture.md`,
`event-versioning.md`, `correlation-ids.md`, ADR-006.

## CURRENT STATE

Two independent, colliding Qt event buses exist today (CONFIRMED — see
`docs/architecture/06-event-architecture.md` for the full source-level finding). This
document defines their planned replacement; it does not describe current behavior further
than that cross-reference.

## TARGET STATE (PROPOSED)

**One** event stream, published only by the Python backend over the `GET /events` SSE
endpoint (`docs/architecture/05-ipc-architecture.md`), relayed unmodified by Tauri, consumed
by React.

**Envelope** (every event, no exceptions):

```json
{
  "event": "analysis.progress",
  "version": 1,
  "correlation_id": "an-8f3c...",
  "investigation_id": "inv-1029",
  "timestamp": "2026-08-20T10:15:32Z",
  "payload": { "...": "..." }
}
```

**Naming convention:** `domain.action` — `analysis.*`, `investigation.*`, `ti.enrichment.*` —
chosen specifically to prevent the current two-bus naming collision
(`investigation_deleted` vs. `investigation_removed` for the same real event).

**Canonical event catalog** (representative; Master Plan §16):

`analysis.started`, `analysis.progress`, `analysis.completed`, `analysis.failed`,
`investigation.created`, `investigation.updated`, `investigation.deleted`,
`ti.enrichment.started`, `ti.enrichment.completed`, `ti.enrichment.failed`.

**Rule:** an event name is defined exactly once, in exactly one place (this document's
eventual full schema set), and every publisher and subscriber references that single
definition — there is no second, informally-named event for the same real-world occurrence.
This rule exists specifically to prevent a recurrence of the current dual-bus problem.

## KNOWN DUPLICATION (Pre-2A Foundation Note)

`frontend/src/shared/events/types.ts` currently hand-mirrors the `EventName` union and
envelope shape defined here rather than being generated from a single source of truth. This
is acceptable at foundation stage (`GET /events` is not yet live — see
`docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md` §6 — so there is no live schema drift risk
yet), but it is a real future hardening item: once events are actually emitted, a manually
maintained TS mirror can silently drift from the Python/pydantic definition. Recommended
direction (not implemented here): generate the TS types from the Python schema (or a shared
JSON Schema) as part of whichever phase wires up real SSE, rather than building a
code-generation pipeline now with nothing yet to generate against.

## MIGRATION NOTES

Built in Phase 4D against a throwaway test client before Rust or React exist, so the schema
is proven correct in isolation first (Master Plan §26).

## UNKNOWN / REQUIRES VERIFICATION

Whether any existing test exercises the interaction between the two current Qt buses:
**UNKNOWN — VERIFY IN PHASE 4B** (see `docs/testing/testing-architecture.md`).
