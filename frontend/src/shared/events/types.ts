/**
 * Event boundary types.
 *
 * Mirrors the SSE event envelope in `docs/contracts/event-model.md`.
 * `GET /events` is now a real `StreamingResponse`
 * (`docs/phase4/PHASE4D_SSE_PART3_IMPLEMENTATION.md`) — this shape was
 * re-verified directly against the actual wire producer this Part
 * (Phase 4D SSE Part 4A), `Event.to_dict()`
 * (`app/application/events.py`) via `_format_sse_event`
 * (`app/api/app.py`), not assumed from this file's own prior draft.
 * Two corrections came out of that: `investigation_id` is a JSON
 * number (Python `int | None`), not a string, and `event_id` — present
 * on every `Event` dataclass instance and therefore in every `data:`
 * payload — was missing entirely.
 *
 * Only `analysis.*` and `ti.enrichment.*` are currently emitted by any
 * command handler (confirmed by reading `app/application/handlers.py`
 * directly). `investigation.*` stays in `EventName` because
 * `docs/contracts/event-model.md` documents it as part of the vocabulary,
 * but no frontend behavior should assume it is live yet — see
 * `docs/phase4/PHASE4D_SSE_PART4A_IMPLEMENTATION.md`.
 */

/** `domain.action` naming convention — see event-model.md. */
export type EventName =
  | "analysis.started"
  | "analysis.progress"
  | "analysis.completed"
  | "analysis.failed"
  | "investigation.created"
  | "investigation.updated"
  | "investigation.deleted"
  | "ti.enrichment.started"
  | "ti.enrichment.completed"
  | "ti.enrichment.failed";

export interface SocIqEvent<TPayload = unknown> {
  event: EventName;
  version: number;
  correlation_id: string;
  investigation_id: number | null;
  timestamp: string;
  payload: TPayload;
  event_id: string;
}
