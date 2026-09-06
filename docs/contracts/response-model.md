# Response Model

**Status:** Documentation Foundation (Phase 4A). Architectural contract only.
**Related:** `command-model.md`, `error-model.md`, `dto-boundaries.md`.

## CURRENT STATE

No response model exists today — see `command-model.md` current-state note.

## TARGET STATE (PROPOSED)

Every command response is a JSON object with a consistent envelope shape:

```json
{
  "success": true,
  "data": { "...": "..." },
  "error": null
}
```

or, on failure:

```json
{
  "success": false,
  "data": null,
  "error": { "code": "INVESTIGATION_NOT_FOUND", "message": "..." }
}
```

The `data` shape is command-specific and defined per-command at implementation time (Phase
4D); the envelope (`success`/`data`/`error`) is fixed across all commands so frontend response
handling does not need per-command special-casing to detect failure.

Long-running commands (e.g. `analyze_report`) return an immediate acknowledgment response
(e.g. `{ "success": true, "data": { "analysis_id": "an-..." } }`) and communicate final
outcome via the event stream (`event-model.md`), not via a delayed HTTP response — the HTTP
layer never blocks for the duration of an analysis.

## MIGRATION NOTES

Exact per-command `data` schemas are implementation work for Phase 4D, informed by the
Phase 4B service-return-shape inventory referenced in
`docs/architecture/02-python-backend-architecture.md`.

## UNKNOWN / REQUIRES VERIFICATION

Exact current return shapes of `app/services/*` (dashboard, correlation, risk-explanation,
system-health) — **UNKNOWN — VERIFY IN PHASE 4B** — needed before per-command `data` schemas
can be written precisely rather than provisionally.
