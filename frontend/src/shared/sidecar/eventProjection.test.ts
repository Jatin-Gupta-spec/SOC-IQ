/**
 * Tests for the Phase 4E-P3 Part 2D-3B pure projection mapping
 * (`eventProjection.ts`). Exercises `projectSidecarEvent` directly —
 * no store, no subscription — since it is a pure function of
 * `(currentState, domainEvent) -> nextState | null`. Integration with
 * the real `SidecarEventSubscription`/`SidecarProjectionStore` pair is
 * covered separately in `projectionConnector.test.ts`.
 */

import { describe, expect, it } from "vitest";

import type { SidecarDomainEvent } from "./eventSubscription";
import { projectSidecarEvent } from "./eventProjection";
import type {
  RestartExhaustedPayload,
  RestartScheduledPayload,
  SidecarStatus,
  StateChangedPayload,
} from "./types";

const TIMESTAMP = "2026-08-25T09:47:00Z";

function status(overrides: Partial<SidecarStatus> = {}): SidecarStatus {
  return {
    state: "RUNNING",
    restart_pending: false,
    restart_pending_attempt: null,
    restart_attempts: 0,
    restart_exhausted: false,
    sequence: 1,
    ...overrides,
  };
}

function stateChanged(
  overrides: Partial<StateChangedPayload> = {},
): SidecarDomainEvent {
  return {
    kind: "state_changed",
    payload: {
      state: "RUNNING",
      previous_state: "STARTING",
      reason: null,
      sequence: 1,
      generation: 1,
      timestamp: TIMESTAMP,
      ...overrides,
    },
  };
}

function restartScheduled(
  overrides: Partial<RestartScheduledPayload> = {},
): SidecarDomainEvent {
  return {
    kind: "restart_scheduled",
    payload: {
      attempt: 1,
      delay_ms: 1000,
      sequence: 1,
      timestamp: TIMESTAMP,
      ...overrides,
    },
  };
}

function restartExhausted(
  overrides: Partial<RestartExhaustedPayload> = {},
): SidecarDomainEvent {
  return {
    kind: "restart_exhausted",
    payload: {
      attempts: 5,
      code: "SIDECAR_RESTART_EXHAUSTED",
      sequence: 1,
      timestamp: TIMESTAMP,
      ...overrides,
    },
  };
}

// ---------------------------------------------------------------------------
// state_changed
// ---------------------------------------------------------------------------

describe("state_changed", () => {
  it("establishes a first projection from null, with backend-verified initial restart defaults", () => {
    const next = projectSidecarEvent(
      null,
      stateChanged({ state: "STARTING", previous_state: "NOT_STARTED", sequence: 1 }),
    );

    expect(next).toEqual(
      status({
        state: "STARTING",
        sequence: 1,
        restart_pending: false,
        restart_pending_attempt: null,
        restart_attempts: 0,
        restart_exhausted: false,
      }),
    );
  });

  it("replaces state and sequence, preserving unrelated restart fields", () => {
    const current = status({
      state: "RUNNING",
      sequence: 5,
      restart_pending: true,
      restart_pending_attempt: 2,
      restart_attempts: 2,
      restart_exhausted: false,
    });

    const next = projectSidecarEvent(
      current,
      stateChanged({ state: "CRASHED", previous_state: "RUNNING", sequence: 6 }),
    );

    expect(next).toEqual(
      status({
        state: "CRASHED",
        sequence: 6,
        restart_pending: true,
        restart_pending_attempt: 2,
        restart_attempts: 2,
        restart_exhausted: false,
      }),
    );
  });

  it("preserves a null restart_pending_attempt untouched", () => {
    const current = status({ restart_pending_attempt: null });
    const next = projectSidecarEvent(current, stateChanged({ state: "STOPPED", sequence: 9 }));
    expect(next?.restart_pending_attempt).toBeNull();
  });

  it("never generates, increments, or reinterprets sequence — preserves it verbatim", () => {
    const next = projectSidecarEvent(null, stateChanged({ sequence: 42, state: "STARTING" }));
    expect(next?.sequence).toBe(42);
  });
});

// ---------------------------------------------------------------------------
// restart_scheduled
// ---------------------------------------------------------------------------

describe("restart_scheduled", () => {
  it("returns null when there is no baseline state to merge onto", () => {
    const next = projectSidecarEvent(null, restartScheduled({ attempt: 1, sequence: 1 }));
    expect(next).toBeNull();
  });

  it("sets restart_pending, restart_pending_attempt, and restart_attempts from attempt; clears restart_exhausted", () => {
    const current = status({ state: "CRASHED", sequence: 3, restart_exhausted: false });

    const next = projectSidecarEvent(current, restartScheduled({ attempt: 2, sequence: 4 }));

    expect(next).toEqual(
      status({
        state: "CRASHED",
        sequence: 4,
        restart_pending: true,
        restart_pending_attempt: 2,
        restart_attempts: 2,
        restart_exhausted: false,
      }),
    );
  });

  it("preserves state (not present in this payload)", () => {
    const current = status({ state: "FAILED" });
    const next = projectSidecarEvent(current, restartScheduled({ attempt: 1 }));
    expect(next?.state).toBe("FAILED");
  });

  it("preserves sequence verbatim from the payload", () => {
    const current = status();
    const next = projectSidecarEvent(current, restartScheduled({ attempt: 1, sequence: 77 }));
    expect(next?.sequence).toBe(77);
  });
});

// ---------------------------------------------------------------------------
// restart_exhausted
// ---------------------------------------------------------------------------

describe("restart_exhausted", () => {
  it("returns null when there is no baseline state to merge onto", () => {
    const next = projectSidecarEvent(null, restartExhausted({ attempts: 5, sequence: 1 }));
    expect(next).toBeNull();
  });

  it("sets restart_attempts/restart_exhausted and clears restart_pending/restart_pending_attempt", () => {
    const current = status({
      state: "CRASHED",
      sequence: 6,
      restart_pending: true,
      restart_pending_attempt: 5,
      restart_attempts: 4,
    });

    const next = projectSidecarEvent(current, restartExhausted({ attempts: 5, sequence: 7 }));

    expect(next).toEqual(
      status({
        state: "CRASHED",
        sequence: 7,
        restart_pending: false,
        restart_pending_attempt: null,
        restart_attempts: 5,
        restart_exhausted: true,
      }),
    );
  });

  it("preserves state (not present in this payload)", () => {
    const current = status({ state: "TIMEOUT" });
    const next = projectSidecarEvent(current, restartExhausted({ attempts: 5 }));
    expect(next?.state).toBe("TIMEOUT");
  });

  it("preserves sequence verbatim from the payload", () => {
    const current = status();
    const next = projectSidecarEvent(current, restartExhausted({ attempts: 5, sequence: 99 }));
    expect(next?.sequence).toBe(99);
  });
});

// ---------------------------------------------------------------------------
// Multi-event sequences
// ---------------------------------------------------------------------------

describe("multi-event sequences", () => {
  it("state_changed -> restart_scheduled -> state_changed -> restart_exhausted projects correctly at each step", () => {
    let state = projectSidecarEvent(
      null,
      stateChanged({ state: "CRASHED", previous_state: "RUNNING", sequence: 1 }),
    );
    expect(state).toEqual(
      status({ state: "CRASHED", sequence: 1, restart_pending: false, restart_attempts: 0 }),
    );

    state = projectSidecarEvent(state, restartScheduled({ attempt: 1, sequence: 2 }));
    expect(state).toEqual(
      status({
        state: "CRASHED",
        sequence: 2,
        restart_pending: true,
        restart_pending_attempt: 1,
        restart_attempts: 1,
        restart_exhausted: false,
      }),
    );

    state = projectSidecarEvent(
      state,
      stateChanged({ state: "RUNNING", previous_state: "STARTING", sequence: 3 }),
    );
    expect(state).toEqual(
      status({
        state: "RUNNING",
        sequence: 3,
        restart_pending: true,
        restart_pending_attempt: 1,
        restart_attempts: 1,
        restart_exhausted: false,
      }),
    );

    state = projectSidecarEvent(state, restartExhausted({ attempts: 5, sequence: 4 }));
    expect(state).toEqual(
      status({
        state: "RUNNING",
        sequence: 4,
        restart_pending: false,
        restart_pending_attempt: null,
        restart_attempts: 5,
        restart_exhausted: true,
      }),
    );
  });
});
