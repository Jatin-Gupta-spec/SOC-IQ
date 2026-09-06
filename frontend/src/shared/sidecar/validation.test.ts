/**
 * Focused tests for the Phase 4E-P3 Part 2D-1 runtime validators.
 *
 * Pure functions, no mocking needed (no `@tauri-apps/api` dependency
 * in this module at all) — unlike `client.test.ts`, which mocks the
 * Tauri IPC boundary because `client.ts` actually calls it.
 */

import { describe, expect, it } from "vitest";

import { LIFECYCLE_STATES } from "./types";
import {
  isRestartExhaustedPayload,
  isRestartScheduledPayload,
  isSidecarStatus,
  isStateChangedPayload,
} from "./validation";

const VALID_TIMESTAMP = "2026-08-25T09:47:00Z";

describe("lifecycle state (via isStateChangedPayload)", () => {
  it.each(LIFECYCLE_STATES)("accepts %s as both state and previous_state", (state) => {
    expect(
      isStateChangedPayload({
        state,
        previous_state: state,
        reason: null,
        sequence: 1,
        generation: 1,
        timestamp: VALID_TIMESTAMP,
      }),
    ).toBe(true);
  });

  it("rejects RESTARTING", () => {
    expect(
      isStateChangedPayload({
        state: "RESTARTING",
        previous_state: "CRASHED",
        reason: null,
        sequence: 1,
        generation: 1,
        timestamp: VALID_TIMESTAMP,
      }),
    ).toBe(false);
  });

  it("rejects a random string", () => {
    expect(
      isStateChangedPayload({
        state: "banana",
        previous_state: "RUNNING",
        reason: null,
        sequence: 1,
        generation: 1,
        timestamp: VALID_TIMESTAMP,
      }),
    ).toBe(false);
  });

  it("rejects an empty string", () => {
    expect(
      isStateChangedPayload({
        state: "",
        previous_state: "RUNNING",
        reason: null,
        sequence: 1,
        generation: 1,
        timestamp: VALID_TIMESTAMP,
      }),
    ).toBe(false);
  });
});

describe("isStateChangedPayload", () => {
  const base = {
    state: "RUNNING",
    previous_state: "STARTING",
    reason: null,
    sequence: 42,
    generation: 1,
    timestamp: VALID_TIMESTAMP,
  };

  it("accepts a valid payload with reason: null", () => {
    expect(isStateChangedPayload(base)).toBe(true);
  });

  it("accepts a valid payload with a present reason", () => {
    expect(
      isStateChangedPayload({
        ...base,
        state: "CRASHED",
        reason: { code: "SIDECAR_UNEXPECTED_EXIT", message: "exit code 1" },
      }),
    ).toBe(true);
  });

  it("rejects a missing sequence", () => {
    const { sequence: _sequence, ...rest } = base;
    expect(isStateChangedPayload(rest)).toBe(false);
  });

  it("rejects a negative sequence", () => {
    expect(isStateChangedPayload({ ...base, sequence: -1 })).toBe(false);
  });

  it("rejects a non-integer sequence", () => {
    expect(isStateChangedPayload({ ...base, sequence: 1.5 })).toBe(false);
  });

  it("rejects an invalid current state", () => {
    expect(isStateChangedPayload({ ...base, state: "RESTARTING" })).toBe(false);
  });

  it("rejects an invalid previous state", () => {
    expect(isStateChangedPayload({ ...base, previous_state: "nope" })).toBe(
      false,
    );
  });

  it("rejects a malformed timestamp", () => {
    expect(
      isStateChangedPayload({ ...base, timestamp: "not-a-timestamp" }),
    ).toBe(false);
  });

  it("rejects a calendar-invalid timestamp", () => {
    expect(
      isStateChangedPayload({ ...base, timestamp: "2026-02-30T00:00:00Z" }),
    ).toBe(false);
  });

  it("rejects a malformed reason object", () => {
    expect(
      isStateChangedPayload({ ...base, reason: { code: "X" } }),
    ).toBe(false);
  });

  it("rejects null, undefined, and non-objects", () => {
    expect(isStateChangedPayload(null)).toBe(false);
    expect(isStateChangedPayload(undefined)).toBe(false);
    expect(isStateChangedPayload("not an object")).toBe(false);
    expect(isStateChangedPayload(42)).toBe(false);
    expect(isStateChangedPayload([])).toBe(false);
  });
});

describe("isRestartScheduledPayload", () => {
  const base = {
    attempt: 1,
    delay_ms: 1000,
    sequence: 7,
    timestamp: VALID_TIMESTAMP,
  };

  it("accepts a valid payload", () => {
    expect(isRestartScheduledPayload(base)).toBe(true);
  });

  it("rejects a missing attempt", () => {
    const { attempt: _attempt, ...rest } = base;
    expect(isRestartScheduledPayload(rest)).toBe(false);
  });

  it("rejects attempt 0 (attempts are 1-based)", () => {
    expect(isRestartScheduledPayload({ ...base, attempt: 0 })).toBe(false);
  });

  it("rejects a negative attempt", () => {
    expect(isRestartScheduledPayload({ ...base, attempt: -1 })).toBe(false);
  });

  it("rejects an invalid (negative) delay_ms", () => {
    expect(isRestartScheduledPayload({ ...base, delay_ms: -100 })).toBe(false);
  });

  it("rejects a non-integer delay_ms", () => {
    expect(isRestartScheduledPayload({ ...base, delay_ms: 100.5 })).toBe(
      false,
    );
  });

  it("rejects an invalid sequence", () => {
    expect(isRestartScheduledPayload({ ...base, sequence: -1 })).toBe(false);
  });

  it("rejects a malformed timestamp", () => {
    expect(
      isRestartScheduledPayload({ ...base, timestamp: "banana" }),
    ).toBe(false);
  });
});

describe("isRestartExhaustedPayload", () => {
  const base = {
    attempts: 5,
    code: "SIDECAR_RESTART_EXHAUSTED",
    sequence: 12,
    timestamp: VALID_TIMESTAMP,
  };

  it("accepts a valid payload", () => {
    expect(isRestartExhaustedPayload(base)).toBe(true);
  });

  it("rejects attempts 0", () => {
    expect(isRestartExhaustedPayload({ ...base, attempts: 0 })).toBe(false);
  });

  it("rejects a negative attempts count", () => {
    expect(isRestartExhaustedPayload({ ...base, attempts: -3 })).toBe(false);
  });

  it("rejects a non-integer attempts count", () => {
    expect(isRestartExhaustedPayload({ ...base, attempts: 2.2 })).toBe(false);
  });

  it("rejects an invalid sequence", () => {
    expect(isRestartExhaustedPayload({ ...base, sequence: -1 })).toBe(false);
  });

  it("rejects an empty code", () => {
    expect(isRestartExhaustedPayload({ ...base, code: "" })).toBe(false);
  });

  it("rejects a malformed timestamp", () => {
    expect(
      isRestartExhaustedPayload({ ...base, timestamp: "2026/08/25" }),
    ).toBe(false);
  });
});

describe("isSidecarStatus", () => {
  const base = {
    state: "RUNNING",
    restart_pending: false,
    restart_pending_attempt: null,
    restart_attempts: 0,
    restart_exhausted: false,
    sequence: 3,
  };

  it("accepts a valid snapshot with no pending restart", () => {
    expect(isSidecarStatus(base)).toBe(true);
  });

  it("accepts a valid snapshot with a pending restart", () => {
    expect(
      isSidecarStatus({
        ...base,
        state: "CRASHED",
        restart_pending: true,
        restart_pending_attempt: 2,
        restart_attempts: 1,
      }),
    ).toBe(true);
  });

  it("accepts a valid exhausted snapshot", () => {
    expect(
      isSidecarStatus({
        ...base,
        state: "FAILED",
        restart_attempts: 5,
        restart_exhausted: true,
      }),
    ).toBe(true);
  });

  it("rejects an invalid state", () => {
    expect(isSidecarStatus({ ...base, state: "RESTARTING" })).toBe(false);
  });

  it("rejects an invalid sequence", () => {
    expect(isSidecarStatus({ ...base, sequence: -1 })).toBe(false);
  });

  it("rejects a non-boolean restart_pending", () => {
    expect(isSidecarStatus({ ...base, restart_pending: "yes" })).toBe(false);
  });

  it("rejects a restart_pending_attempt of 0", () => {
    expect(
      isSidecarStatus({ ...base, restart_pending_attempt: 0 }),
    ).toBe(false);
  });

  it("rejects a negative restart_attempts", () => {
    expect(isSidecarStatus({ ...base, restart_attempts: -1 })).toBe(false);
  });

  it("rejects a non-boolean restart_exhausted", () => {
    expect(isSidecarStatus({ ...base, restart_exhausted: 1 })).toBe(false);
  });

  it("rejects null and non-objects", () => {
    expect(isSidecarStatus(null)).toBe(false);
    expect(isSidecarStatus("status")).toBe(false);
    expect(isSidecarStatus([])).toBe(false);
  });
});
