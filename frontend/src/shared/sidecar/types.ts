/**
 * Frontend-side contract for the Tauri sidecar lifecycle events and
 * the `get_sidecar_status` command — Phase 4E-P3 Part 2D-1.
 *
 * Mirrors, field-for-field, the source of truth in
 * `src-tauri/src/events.rs` (event payload structs) and
 * `src-tauri/src/lib.rs`'s `get_sidecar_status` (the `SidecarStatus`
 * DTO it returns). Nothing here is invented: every field name/type is
 * a mechanical transcription of the Rust struct it comes from, the
 * same convention `shared/api/types.ts` already established for the
 * command contract (see that file's own doc comment).
 *
 * This module defines SHAPES and constants only. It does not
 * subscribe to Tauri events (Part 2D-2), does not hold state
 * (Part 2D-3), and renders nothing (no UI in any part of 2D-1).
 *
 * # Wire format
 *
 * Every backend struct these types mirror derives `serde::Serialize`
 * with no `#[serde(rename...)]`/`#[serde(rename_all...)]` attribute
 * anywhere in `events.rs` or on `SidecarStatus` in `lib.rs` (grep-
 * confirmed) — so serde's default (Rust field name verbatim) is what
 * actually crosses the wire. Every field below therefore keeps the
 * backend's own snake_case name unchanged, exactly as
 * `shared/api/types.ts` already does for the command contract,
 * rather than introducing an undocumented camelCase remapping.
 *
 * Rust numeric widths (`u64`/`u32`) do not exist in JSON/TypeScript;
 * serde_json emits them as plain JSON numbers, so every one of them
 * is typed `number` here. `Option<T>` fields are typed `T | null`,
 * matching serde_json's default `Option::None -> null` /
 * `Option::Some(v) -> v` encoding (not `T | undefined` — Tauri's IPC
 * layer serializes through JSON, which has no `undefined`).
 */

// ---------------------------------------------------------------------------
// Lifecycle state — mirrors sidecar-core/src/state.rs::LifecycleState's
// `Display` impl (the exact 8 wire strings `state_name()` in events.rs
// produces via `LifecycleState::to_string()`).
// ---------------------------------------------------------------------------

/**
 * The backend's authoritative FSM states, verbatim. Deliberately does
 * NOT include `RESTARTING` or any other frontend-only state — the
 * backend FSM (`sidecar-core::state::Lifecycle`) has no such variant,
 * and this contract must not invent one (task brief §8/§33).
 */
export const LIFECYCLE_STATES = [
  "NOT_STARTED",
  "STARTING",
  "RUNNING",
  "CRASHED",
  "STOPPING",
  "STOPPED",
  "FAILED",
  "TIMEOUT",
] as const;

export type LifecycleState = (typeof LIFECYCLE_STATES)[number];

// ---------------------------------------------------------------------------
// Event names — mirrors events.rs's EVENT_STATE_CHANGED /
// EVENT_RESTART_SCHEDULED / EVENT_RESTART_EXHAUSTED constants exactly.
// ---------------------------------------------------------------------------

/** Mirrors `events::EVENT_STATE_CHANGED` (`src-tauri/src/events.rs`). */
export const EVENT_STATE_CHANGED = "sidecar:state_changed" as const;

/** Mirrors `events::EVENT_RESTART_SCHEDULED`. */
export const EVENT_RESTART_SCHEDULED = "sidecar:restart_scheduled" as const;

/** Mirrors `events::EVENT_RESTART_EXHAUSTED`. */
export const EVENT_RESTART_EXHAUSTED = "sidecar:restart_exhausted" as const;

/**
 * The complete, closed set of canonical sidecar lifecycle event
 * names. There must be no competing spelling anywhere in the
 * frontend (task brief §9) — e.g. no `sidecar:restarting`,
 * `sidecar:recovered`, `sidecar:started`, `sidecar:crashed`. Future
 * code (Part 2D-2's subscriber) should reference these constants,
 * never a raw string literal.
 */
export const SIDECAR_EVENT_NAMES = [
  EVENT_STATE_CHANGED,
  EVENT_RESTART_SCHEDULED,
  EVENT_RESTART_EXHAUSTED,
] as const;

export type SidecarEventName = (typeof SIDECAR_EVENT_NAMES)[number];

// ---------------------------------------------------------------------------
// StateChangeReason — mirrors events.rs::StateChangeReason
// ---------------------------------------------------------------------------

/**
 * Mirrors `events::StateChangeReason`. `code` reuses
 * `SidecarError::code()` verbatim (see `sidecar-core/src/error.rs`);
 * `message` reuses `SidecarError::to_string()` verbatim. No second
 * error-code vocabulary is introduced here (task brief §17: "do not
 * expand the error contract").
 */
export interface StateChangeReason {
  readonly code: string;
  readonly message: string;
}

/**
 * The nine `SidecarError::code()` values as currently defined in
 * `sidecar-core/src/error.rs`. Provided for documentation/narrowing
 * convenience only — `StateChangeReason.code` and
 * `RestartExhaustedPayload.code` remain typed `string`, not this
 * union, since the backend's own `code()` method returns `&'static
 * str`, not a closed Rust enum serialized as a string; treating it as
 * a closed frontend union would be inventing a stronger contract than
 * the backend actually gives (task brief §17: "do not invent frontend
 * lifecycle error codes").
 */
export const KNOWN_SIDECAR_ERROR_CODES = [
  "SIDECAR_INVALID_TRANSITION",
  "SIDECAR_SPAWN_FAILURE",
  "SIDECAR_STARTUP_TIMEOUT",
  "SIDECAR_HANDSHAKE_FAILURE",
  "SIDECAR_HEALTH_CHECK_FAILURE",
  "SIDECAR_UNEXPECTED_EXIT",
  "SIDECAR_SHUTDOWN_FAILURE",
  "SIDECAR_INVALID_STARTUP_OUTPUT",
  "SIDECAR_RESTART_EXHAUSTED",
] as const;

// ---------------------------------------------------------------------------
// Event payloads — mirrors events.rs's StateChangedPayload /
// RestartScheduledPayload / RestartExhaustedPayload exactly.
// ---------------------------------------------------------------------------

/**
 * Mirrors `events::StateChangedPayload`.
 *
 * | field            | rust type              | required | meaning                                             | backend source |
 * |------------------|-------------------------|----------|-------------------------------------------------------|----------------|
 * | `state`          | `String`                | yes      | the new (current) lifecycle state                      | `state_name(current)` |
 * | `previous_state`  | `String`                | yes      | the state transitioned from                            | `state_name(previous)` |
 * | `reason`         | `Option<StateChangeReason>` | no (`null` when absent) | present only when the transition's origin was a `SidecarError` | `reason.map(StateChangeReason::from)` |
 * | `sequence`       | `u64`                    | yes      | this event's allocated sequence — opaque ordering value, never regenerate/reinterpret (task brief §18) | `sequencer.next_sequence()` |
 * | `generation`     | `u32`                    | yes      | bumped once per real `NOT_STARTED -> STARTING` transition | `sequencer.current_generation()` |
 * | `timestamp`      | `String` (RFC 3339 UTC) | yes      | metadata only — never used for ordering (task brief §19) | `rfc3339_now()` |
 */
export interface StateChangedPayload {
  readonly state: LifecycleState;
  readonly previous_state: LifecycleState;
  readonly reason: StateChangeReason | null;
  readonly sequence: number;
  readonly generation: number;
  readonly timestamp: string;
}

/**
 * Mirrors `events::RestartScheduledPayload`.
 *
 * | field       | rust type | required | meaning                                                              | backend source |
 * |-------------|-----------|----------|-------------------------------------------------------------------------|----------------|
 * | `attempt`   | `u32`     | yes      | the accepted attempt number                                             | `RestartDecision::Retry::attempt` |
 * | `delay_ms`  | `u64`     | yes      | the accepted backoff delay in milliseconds, never recomputed frontend-side | `Retry::after` |
 * | `sequence`  | `u64`     | yes      | opaque ordering value from the one `EventSequencer`                     | `sequencer.next_sequence()` |
 * | `timestamp` | `String`  | yes      | metadata only, moment `schedule()` was confirmed accepted               | `rfc3339_now()` |
 */
export interface RestartScheduledPayload {
  readonly attempt: number;
  readonly delay_ms: number;
  readonly sequence: number;
  readonly timestamp: string;
}

/**
 * Mirrors `events::RestartExhaustedPayload`.
 *
 * | field       | rust type | required | meaning                                                | backend source |
 * |-------------|-----------|----------|-----------------------------------------------------------|----------------|
 * | `attempts`  | `u32`     | yes      | final attempt count when exhaustion was observed          | `RestartDecision::Exhausted::attempts` |
 * | `code`      | `String`  | yes      | always `"SIDECAR_RESTART_EXHAUSTED"` today, reused verbatim from `SidecarError::code()` | `err.code()` |
 * | `sequence`  | `u64`     | yes      | opaque ordering value                                      | `sequencer.next_sequence()` |
 * | `timestamp` | `String`  | yes      | metadata only                                              | `rfc3339_now()` |
 */
export interface RestartExhaustedPayload {
  readonly attempts: number;
  readonly code: string;
  readonly sequence: number;
  readonly timestamp: string;
}

// ---------------------------------------------------------------------------
// SidecarStatus — mirrors lib.rs::SidecarStatus (the get_sidecar_status
// return type), which is itself defined in events.rs.
// ---------------------------------------------------------------------------

/**
 * Mirrors `events::SidecarStatus`, the return type of the
 * `get_sidecar_status` Tauri command (`lib.rs`). A read-only,
 * point-in-time snapshot — never mutated locally, never used to
 * derive a second lifecycle authority (task brief §33).
 *
 * | field                       | rust type      | required | meaning                                            | backend source |
 * |------------------------------|----------------|----------|-------------------------------------------------------|----------------|
 * | `state`                      | `String`       | yes      | current authoritative lifecycle state                  | `state.process` |
 * | `restart_pending`            | `bool`         | yes      | whether a restart is currently scheduled               | `state.scheduler.is_pending()` |
 * | `restart_pending_attempt`    | `Option<u32>`  | no (`null` when absent) | the attempt number of the pending restart, if any      | `state.scheduler.pending_attempt()` |
 * | `restart_attempts`           | `u32`          | yes      | current attempt count for this crash-loop window       | `state.restart_tracker` |
 * | `restart_exhausted`          | `bool`         | yes      | `true` exactly when `attempts >= max_attempts` right now | `status_restart_exhausted(...)` |
 * | `sequence`                   | `u64`          | yes      | latest already-allocated event sequence — a peek, never a new allocation | `state.events.current_sequence()` |
 */
export interface SidecarStatus {
  readonly state: LifecycleState;
  readonly restart_pending: boolean;
  readonly restart_pending_attempt: number | null;
  readonly restart_attempts: number;
  readonly restart_exhausted: boolean;
  readonly sequence: number;
}

/** Mirrors the `get_sidecar_status` Tauri command's own name, for a
 * future `invoke()` call site (Part 2D-2+) to reference instead of a
 * raw string literal — established here since it belongs with the
 * rest of this contract, not because this checkpoint calls it. */
export const COMMAND_GET_SIDECAR_STATUS = "get_sidecar_status" as const;
