# Correlation IDs

**Status:** Documentation Foundation (Phase 4A).
**Related:** `event-model.md`, `command-model.md`, Master Plan §15, §21,
`docs/architecture/19-observability-architecture.md`.

## CURRENT STATE

No correlation-id concept exists today (CONFIRMED — not present in any Signal definition in
`application_events.py` or `event_bus.py`).

## TARGET STATE (PROPOSED)

- Every long-running command (e.g. `analyze_report`) is assigned a `correlation_id` at the
  moment it's accepted, returned in the command's immediate acknowledgment response
  (`response-model.md`), and attached to every subsequent event related to that operation
  (`analysis.started` → `analysis.progress` ×N → `analysis.completed`/`failed`).
- `investigation_id` is carried separately from `correlation_id` on events where relevant —
  a single analysis run (`correlation_id`) may create or update one `investigation_id`, but
  the two ids serve different purposes: `correlation_id` ties together one operation's
  lifecycle; `investigation_id` identifies the durable domain entity the operation acted on.
- The same `correlation_id` appears in structured log lines (see
  `docs/architecture/19-observability-architecture.md`), so a support/debugging session can
  trace one operation across the event stream and the backend logs using a single id.

## MIGRATION NOTES

Introduced alongside the command/event model in Phase 4D — there is no legacy correlation
scheme to reconcile with.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding.
