/**
 * Runtime validators for the sidecar lifecycle contract —
 * Phase 4E-P3 Part 2D-1.
 *
 * TypeScript's compile-time types (`types.ts`) say nothing about what
 * actually arrives over Tauri's IPC boundary at runtime (task brief
 * §10/§21) — a Tauri `Event<T>`'s `payload` is typed `T` only because
 * the caller asserted it, not because anything checked it. These
 * functions are the one place that assertion is actually checked.
 *
 * Pattern used throughout (task brief §21):
 *
 *     unknown -> runtime validator -> typed payload
 *
 * Never `as StateChangedPayload` without going through one of these
 * first.
 *
 * Deliberately small, dependency-free, hand-written predicates — no
 * schema-validation library is introduced (task brief §11: "do not
 * create a giant generic schema framework", "do not add a new
 * dependency unless absolutely necessary"). Every function here is
 * pure and independently unit-testable (see `validation.test.ts`).
 *
 * Malformed-payload policy (task brief §12): every validator returns
 * `false` on malformed input. None of them throw. A future
 * subscriber (Part 2D-2) can safely do:
 *
 *     receive event -> validate -> valid: process / invalid: reject + diagnostic
 *
 * without needing a try/catch around the validation step itself.
 */

import {
  LIFECYCLE_STATES,
  type LifecycleState,
  type RestartExhaustedPayload,
  type RestartScheduledPayload,
  type SidecarStatus,
  type StateChangedPayload,
  type StateChangeReason,
} from "./types";

// ---------------------------------------------------------------------------
// Primitive helpers
// ---------------------------------------------------------------------------

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * A Rust `u32`/`u64` crossing serde_json always arrives as a JSON
 * number. Validated as: an actual `number` (not `NaN`/`Infinity`),
 * integral, and non-negative — a Rust unsigned integer can never
 * legitimately be negative or fractional on this wire.
 */
function isNonNegativeInteger(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    Number.isInteger(value) &&
    value >= 0
  );
}

function isLifecycleState(value: unknown): value is LifecycleState {
  return (
    typeof value === "string" &&
    (LIFECYCLE_STATES as readonly string[]).includes(value)
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

/**
 * Backend contract: `timestamp` is an RFC 3339 UTC string,
 * second-precision, always ending in `Z`
 * (`events.rs::format_rfc3339`, e.g. `"2026-08-25T09:47:00Z"`).
 * Validated structurally against that exact shape rather than with a
 * full RFC 3339 grammar (fractional seconds, explicit `+00:00`
 * offsets, etc. never appear in this backend's own output, so
 * accepting them would validate a looser contract than the backend
 * actually emits). Deliberately does not re-parse into a `Date` for
 * ordering purposes — per task brief §19, timestamps are metadata
 * only and are never used to determine event order.
 */
const RFC3339_UTC_SECONDS_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

function isBackendTimestamp(value: unknown): value is string {
  if (typeof value !== "string" || !RFC3339_UTC_SECONDS_PATTERN.test(value)) {
    return false;
  }
  // Reject calendar-invalid strings that still match the pattern
  // (e.g. "2026-02-30T00:00:00Z") by round-tripping through Date and
  // confirming the UTC fields survive unchanged.
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return false;
  }
  return parsed.toISOString().slice(0, 19) === value.slice(0, 19);
}

// ---------------------------------------------------------------------------
// StateChangeReason
// ---------------------------------------------------------------------------

export function isStateChangeReason(
  value: unknown,
): value is StateChangeReason {
  if (!isPlainObject(value)) return false;
  return (
    isNonEmptyString(value.code) &&
    typeof value.message === "string"
  );
}

// ---------------------------------------------------------------------------
// StateChangedPayload
// ---------------------------------------------------------------------------

export function isStateChangedPayload(
  value: unknown,
): value is StateChangedPayload {
  if (!isPlainObject(value)) return false;

  if (!isLifecycleState(value.state)) return false;
  if (!isLifecycleState(value.previous_state)) return false;

  if (value.reason !== null && !isStateChangeReason(value.reason)) {
    return false;
  }

  if (!isNonNegativeInteger(value.sequence)) return false;
  if (!isNonNegativeInteger(value.generation)) return false;
  if (!isBackendTimestamp(value.timestamp)) return false;

  return true;
}

// ---------------------------------------------------------------------------
// RestartScheduledPayload
// ---------------------------------------------------------------------------

export function isRestartScheduledPayload(
  value: unknown,
): value is RestartScheduledPayload {
  if (!isPlainObject(value)) return false;

  // attempt is a Rust u32 restart-attempt counter: 1-based, so 0 is
  // not a valid attempt number (RestartTracker::decide's own
  // `self.attempts + 1` construction never produces 0).
  if (!isNonNegativeInteger(value.attempt) || value.attempt < 1) {
    return false;
  }
  if (!isNonNegativeInteger(value.delay_ms)) return false;
  if (!isNonNegativeInteger(value.sequence)) return false;
  if (!isBackendTimestamp(value.timestamp)) return false;

  return true;
}

// ---------------------------------------------------------------------------
// RestartExhaustedPayload
// ---------------------------------------------------------------------------

export function isRestartExhaustedPayload(
  value: unknown,
): value is RestartExhaustedPayload {
  if (!isPlainObject(value)) return false;

  // attempts is RestartDecision::Exhausted::attempts, always
  // policy.max_attempts by that type's own invariant, i.e. >= 1 for
  // any policy that allows at least one retry.
  if (!isNonNegativeInteger(value.attempts) || value.attempts < 1) {
    return false;
  }
  if (!isNonEmptyString(value.code)) return false;
  if (!isNonNegativeInteger(value.sequence)) return false;
  if (!isBackendTimestamp(value.timestamp)) return false;

  return true;
}

// ---------------------------------------------------------------------------
// SidecarStatus
// ---------------------------------------------------------------------------

export function isSidecarStatus(value: unknown): value is SidecarStatus {
  if (!isPlainObject(value)) return false;

  if (!isLifecycleState(value.state)) return false;
  if (typeof value.restart_pending !== "boolean") return false;

  if (
    value.restart_pending_attempt !== null &&
    !(
      isNonNegativeInteger(value.restart_pending_attempt) &&
      value.restart_pending_attempt >= 1
    )
  ) {
    return false;
  }

  if (!isNonNegativeInteger(value.restart_attempts)) return false;
  if (typeof value.restart_exhausted !== "boolean") return false;
  if (!isNonNegativeInteger(value.sequence)) return false;

  return true;
}
