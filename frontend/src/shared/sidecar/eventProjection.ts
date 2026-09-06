/**
 * Pure event → `SidecarStatus` projection mapping — Phase 4E-P3
 * Part 2D-3B.
 *
 * This module answers exactly one question: given the projection
 * store's currently held state (`SidecarProjectionState`, Part 2D-3A)
 * and one validated, sequence-accepted `SidecarDomainEvent` (Part
 * 2D-2's `onEvent()` seam), what `SidecarStatus` should the store hold
 * next? It has no side effects of its own — it does not touch
 * `SidecarProjectionStore`, does not subscribe to anything, and is not
 * itself the Part 2D-3B integration (see `projectionConnector.ts` for
 * that). Kept separate specifically so the mapping rules below are
 * testable in complete isolation from both the store and the
 * subscription layer (task brief §11: "Document the exact projection
 * mapping").
 *
 * # Source of truth for every mapping decision below
 *
 * - `src-tauri/src/events.rs` — the three payload structs
 *   (`StateChangedPayload`/`RestartScheduledPayload`/
 *   `RestartExhaustedPayload`) and `SidecarStatus` itself.
 * - `src-tauri/src/lib.rs` — the one real call site per event
 *   (`emit_state_changed`/`emit_restart_scheduled`/
 *   `emit_restart_exhausted`'s callers), which is what establishes the
 *   *relationship* between a payload field and a `SidecarStatus`
 *   field that the payload's own shape does not spell out by itself.
 * - `sidecar-core/src/restart.rs` — `RestartTracker::decide`/
 *   `record_attempt`, which is what proves the `attempt`/`attempts`
 *   equivalences used below.
 *
 * # Field-by-field mapping
 *
 * ## `sidecar:state_changed` → `StateChangedPayload`
 *
 * | `SidecarStatus` field | source |
 * |---|---|
 * | `state` | `payload.state` (replace) |
 * | `sequence` | `payload.sequence` (replace) |
 * | `restart_pending`, `restart_pending_attempt`, `restart_attempts`, `restart_exhausted` | **not present** in this payload at all — left unchanged (merge) |
 *
 * `StateChangedPayload` (`events.rs`) carries no restart-accounting
 * field whatsoever — `lib.rs`'s `emit_state_changed` call sites never
 * read `restart_tracker`/`scheduler` when building it. Resetting those
 * four fields to some other value on every `state_changed` event would
 * be inventing information this event does not carry (task brief §7:
 * "do not invent frontend values"), so they are carried over verbatim
 * from whatever the store already held (task brief §12: "do not
 * arbitrarily reset absent fields").
 *
 * ## `sidecar:restart_scheduled` → `RestartScheduledPayload`
 *
 * | `SidecarStatus` field | source |
 * |---|---|
 * | `restart_pending` | `true` (replace) — this event is only ever emitted once `RestartScheduler::schedule` has actually accepted the attempt (`events.rs`'s own doc on `emit_restart_scheduled`; `lib.rs`'s call site gates on `scheduled == true`) |
 * | `restart_pending_attempt` | `payload.attempt` (replace) |
 * | `restart_attempts` | `payload.attempt` (replace) — `lib.rs`'s `handle_retry_eligible_failure` calls `tracker.record_attempt()` *before* `scheduler.schedule(attempt, ...)`, and `RestartTracker::record_attempt` returns the post-increment count; `RestartDecision::Retry`'s own `attempt` field (`restart.rs::RestartTracker::decide`, `let attempt = self.attempts + 1`) is exactly that same post-increment value. The two are therefore the same number by construction, not independently derived — `get_sidecar_status`'s own `restart_attempts` reads the identical `tracker.attempts()` this payload's `attempt` already equals. |
 * | `restart_exhausted` | `false` (replace) — this event is emitted only from `RestartDecision::Retry`'s arm, never `Exhausted`'s (`handle_retry_eligible_failure`'s `match`) |
 * | `sequence` | `payload.sequence` (replace) |
 * | `state` | **not present** in this payload — left unchanged (merge) |
 *
 * ## `sidecar:restart_exhausted` → `RestartExhaustedPayload`
 *
 * | `SidecarStatus` field | source |
 * |---|---|
 * | `restart_attempts` | `payload.attempts` (replace) — `RestartDecision::Exhausted::attempts` is `tracker.attempts()` unchanged (the `Exhausted` arm never calls `record_attempt` again — `restart.rs`'s own doc), the same counter `get_sidecar_status` reads |
 * | `restart_exhausted` | `true` (replace) |
 * | `restart_pending` | `false` (replace) — reaching `RestartDecision::Exhausted` means `decide()` was consulted *before* any `scheduler.schedule()` call for this failure occurred (`handle_retry_eligible_failure`'s `match` — the `Exhausted` arm never calls `schedule`), so no new restart was scheduled on this path; any restart that *was* previously pending was necessarily already consumed by `RestartSchedule::consume` before its own callback could reach `handle_retry_eligible_failure` again (`restart_scheduler.rs::RestartScheduler::schedule`'s callback: `consume` always runs immediately before `action()`) |
 * | `restart_pending_attempt` | `null` (replace) — same reasoning as `restart_pending` above |
 * | `sequence` | `payload.sequence` (replace) |
 * | `state` | **not present** in this payload — left unchanged (merge) |
 *
 * # What this module deliberately does NOT do
 *
 * It does not infer `restart_pending`/`restart_attempts` transitions
 * from a *different* event kind's `previous_state`/`state` pair (e.g.
 * inferring "the pending restart must have just fired" from a
 * `state_changed` event whose `previous_state` is a terminal state and
 * `state` is `NOT_STARTED`). That inference is real in the backend
 * (`restart_scheduler.rs`'s `schedule()` callback does call `consume`
 * immediately before `attempt_restart` runs), but it is a multi-event,
 * cross-stream correlation the `state_changed` payload itself carries
 * no field for — encoding it here would be reconstructing status from
 * event *sequencing* rather than projecting a single event's own
 * payload, which edges toward the snapshot-reconciliation problem
 * Part 2D-3C explicitly, separately owns (task brief §22/§9: "no
 * snapshot logic", "Part 2D-3C owns snapshot reconciliation"). The
 * practical consequence — `restart_pending` can read stale (`true`)
 * for the brief window between a scheduled restart actually firing
 * and this store's next event — is a known, documented limitation of
 * this checkpoint's event-only scope, not an oversight.
 *
 * # Establishing a first projection (`current === null`)
 *
 * `SidecarStatus` has no partial/optional form — every field is
 * required (task brief §5's own note, `projectionStore.ts`'s module
 * doc). A `restart_scheduled`/`restart_exhausted` event's payload has
 * no `state` field at all, so if the store has never held a
 * `SidecarStatus` yet, there is no backend-sourced value this module
 * could put in `state` — inventing one (e.g. defaulting to
 * `"NOT_STARTED"`) would be exactly the "invent frontend values"
 * violation task brief §7 forbids. `projectSidecarEvent` therefore
 * returns `null` (meaning: no projection possible yet, do not call
 * `applyProjectedState`) for a restart event arriving before any
 * `state_changed` event has ever been projected.
 *
 * A `state_changed` event, by contrast, always carries `state`, so it
 * *can* establish the very first projection on its own. The four
 * restart-accounting fields still need a value in that case — the
 * zero/empty defaults below (`restart_pending: false`,
 * `restart_pending_attempt: null`, `restart_attempts: 0`,
 * `restart_exhausted: false`) are not invented: they are exactly the
 * real values `SidecarState`'s fields hold at construction
 * (`lib.rs`'s `.manage(SidecarState { restart_tracker:
 * Mutex::new(RestartTracker::new()), scheduler:
 * RestartScheduler::new(), ... })` — `RestartTracker::new()` is `{
 * attempts: 0 }`, a fresh `RestartSchedule` has nothing pending), i.e.
 * the correct values for the first `state_changed` event any given
 * application run ever emits (`NOT_STARTED -> STARTING`, `run()`'s
 * `setup` closure). If a store's subscription happens to start
 * mid-stream (after the real first event), this default can be wrong
 * for the same documented reason as the previous section — event-only
 * projection cannot know backend history it never observed; that gap
 * is exactly what a future `get_sidecar_status`-backed snapshot
 * (2D-3C) closes.
 */

import type { SidecarDomainEvent } from "./eventSubscription";
import type { SidecarProjectionState } from "./projectionStore";
import type { SidecarStatus } from "./types";

/**
 * The real, construction-time values of `SidecarState`'s
 * restart-accounting fields (`lib.rs`'s `.manage(...)` call) — see the
 * module doc's "Establishing a first projection" section for why
 * these are backend-verified, not invented.
 */
const INITIAL_RESTART_FIELDS: Pick<
  SidecarStatus,
  "restart_pending" | "restart_pending_attempt" | "restart_attempts" | "restart_exhausted"
> = {
  restart_pending: false,
  restart_pending_attempt: null,
  restart_attempts: 0,
  restart_exhausted: false,
};

/**
 * Project one validated `SidecarDomainEvent` onto the store's current
 * state. Returns the next `SidecarStatus` to apply, or `null` when no
 * projection is possible yet (a restart event arrived before any
 * `state_changed` event ever established a baseline `state` — see the
 * module doc). Never mutates `current` — `SidecarProjectionStore`
 * already hands out a frozen reference (Part 2D-3A), and this function
 * only ever reads it.
 */
export function projectSidecarEvent(
  current: SidecarProjectionState,
  event: SidecarDomainEvent,
): SidecarStatus | null {
  switch (event.kind) {
    case "state_changed": {
      const base: SidecarStatus =
        current ??
        ({
          state: event.payload.state,
          sequence: event.payload.sequence,
          ...INITIAL_RESTART_FIELDS,
        } satisfies SidecarStatus);

      return {
        ...base,
        state: event.payload.state,
        sequence: event.payload.sequence,
      };
    }

    case "restart_scheduled": {
      if (current === null) {
        // No baseline `state` to merge onto yet — see module doc.
        return null;
      }
      return {
        ...current,
        restart_pending: true,
        restart_pending_attempt: event.payload.attempt,
        restart_attempts: event.payload.attempt,
        restart_exhausted: false,
        sequence: event.payload.sequence,
      };
    }

    case "restart_exhausted": {
      if (current === null) {
        // No baseline `state` to merge onto yet — see module doc.
        return null;
      }
      return {
        ...current,
        restart_attempts: event.payload.attempts,
        restart_exhausted: true,
        restart_pending: false,
        restart_pending_attempt: null,
        sequence: event.payload.sequence,
      };
    }
  }
}
