/**
 * Normalized, frontend-facing sidecar status vocabulary — Phase 4G-3
 * Part 1.
 *
 * `SidecarProjectionState` (`projectionStore.ts`) is either `null` or
 * a raw, frozen-contract `SidecarStatus` (`types.ts`): its `state`
 * field is one of the backend's eight FSM strings verbatim, plus two
 * separate boolean flags (`restart_pending`, `restart_exhausted`) a
 * future status UI would otherwise have to combine by hand at every
 * call site. This module is that combination, done once, as a thin,
 * pure projection — not a second source of truth (task brief §5: "do
 * not invent competing status names", "create a thin
 * projection/adapter rather than duplicating the source state
 * model"). It owns no state and subscribes to nothing itself; pair it
 * with `useSidecarStatus()` (`useSidecarStatus.ts`) to get a live
 * value in a component.
 *
 * # Vocabulary (task brief §5)
 *
 * The six variants below are exactly the distinctions task brief §5
 * asks a normalized type to preserve: `"unknown"` (unavailable/
 * unknown), `"starting"`, `"connected"` (running), `"disconnected"`
 * (stopped), `"restarting"`, and `"failure"` (covers both
 * exhausted-restart and a bare crash/failure/timeout — see mapping
 * table below for why these two are not split further). Every
 * variant maps onto states the existing `LIFECYCLE_STATES`/
 * `SidecarStatus` contract already supports; none is a new backend
 * state (task brief §5's closing instruction).
 *
 * # Mapping precedence
 *
 * | condition (checked in order)                        | view            |
 * |-------------------------------------------------------|-----------------|
 * | `state === null` (task brief §6: no snapshot yet)      | `"unknown"`     |
 * | `restart_exhausted === true`                           | `"failure"`     |
 * | `restart_pending === true`                              | `"restarting"`  |
 * | `state.state === "STARTING"`                            | `"starting"`    |
 * | `state.state === "RUNNING"`                              | `"connected"`   |
 * | `state.state` is `"NOT_STARTED"` \| `"STOPPING"` \| `"STOPPED"` | `"disconnected"` |
 * | `state.state` is `"CRASHED"` \| `"FAILED"` \| `"TIMEOUT"`      | `"failure"`     |
 * | anything else (task brief §8: unknown future state)     | `"unknown"`     |
 *
 * `restart_exhausted`/`restart_pending` are checked before `.state`
 * because they are the more specific signal the backend already
 * distinguishes them for (a `CRASHED` process with a restart pending
 * is meaningfully "restarting", not a bare "failure"); once exhausted,
 * no further restart will happen, which is why it takes precedence
 * over a merely-pending one. The final `default` branch is not
 * theoretically reachable against today's frozen `LIFECYCLE_STATES`
 * (task brief §5: "only use states actually supported by the
 * existing source contract") — it exists purely as the task brief §8
 * safe fallback for a value arriving from a future backend version
 * this frontend hasn't been updated for yet, exercised directly by
 * this module's own test file via an intentionally-invalid cast.
 */

import type { SidecarProjectionState } from "./projectionStore";

export const SIDECAR_STATUS_VIEWS = [
  "unknown",
  "starting",
  "connected",
  "disconnected",
  "restarting",
  "failure",
] as const;

export type SidecarStatusView = (typeof SIDECAR_STATUS_VIEWS)[number];

export function projectSidecarStatusView(
  state: SidecarProjectionState,
): SidecarStatusView {
  if (state === null) {
    return "unknown";
  }

  if (state.restart_exhausted) {
    return "failure";
  }

  if (state.restart_pending) {
    return "restarting";
  }

  switch (state.state) {
    case "STARTING":
      return "starting";
    case "RUNNING":
      return "connected";
    case "NOT_STARTED":
    case "STOPPING":
    case "STOPPED":
      return "disconnected";
    case "CRASHED":
    case "FAILED":
    case "TIMEOUT":
      return "failure";
    default:
      // Safe fallback for an unrecognized future backend state
      // (task brief §8) — never throws, never crashes the caller.
      return "unknown";
  }
}
