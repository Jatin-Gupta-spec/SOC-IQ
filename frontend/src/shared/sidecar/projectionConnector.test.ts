/**
 * Tests for the Phase 4E-P3 Part 2D-3B integration
 * (`projectionConnector.ts`) — the complete
 *
 *     fake Tauri listen()
 *       -> real SidecarEventSubscription (Part 2D-2)
 *       -> real SidecarProjectionConnector (Part 2D-3B, this checkpoint)
 *       -> real SidecarProjectionStore (Part 2D-3A)
 *       -> real subscriber behavior
 *
 * path. Per task brief §21: only the external Tauri `listen()`
 * boundary is faked (via `SidecarEventSubscription`'s existing
 * `listenFn` injection seam, the same one `eventSubscription.test.ts`
 * uses) — every other layer here is the real production class.
 */

import { describe, expect, it, vi } from "vitest";

import type { UnlistenFn } from "@tauri-apps/api/event";

import { SidecarEventSubscription } from "./eventSubscription";
import { SidecarProjectionConnector } from "./projectionConnector";
import { SidecarProjectionStore } from "./projectionStore";
import type {
  RestartExhaustedPayload,
  RestartScheduledPayload,
  StateChangedPayload,
} from "./types";

const TIMESTAMP = "2026-08-25T09:47:00Z";

function stateChangedPayload(
  overrides: Partial<StateChangedPayload> = {},
): StateChangedPayload {
  return {
    state: "STARTING",
    previous_state: "NOT_STARTED",
    reason: null,
    sequence: 1,
    generation: 1,
    timestamp: TIMESTAMP,
    ...overrides,
  };
}

function restartScheduledPayload(
  overrides: Partial<RestartScheduledPayload> = {},
): RestartScheduledPayload {
  return {
    attempt: 1,
    delay_ms: 1000,
    sequence: 1,
    timestamp: TIMESTAMP,
    ...overrides,
  };
}

function restartExhaustedPayload(
  overrides: Partial<RestartExhaustedPayload> = {},
): RestartExhaustedPayload {
  return {
    attempts: 5,
    code: "SIDECAR_RESTART_EXHAUSTED",
    sequence: 1,
    timestamp: TIMESTAMP,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Fake listen() — the one external boundary this suite fakes
// ---------------------------------------------------------------------------

interface FakeRegistration {
  readonly eventName: string;
  readonly handler: (event: { payload: unknown }) => void;
  active: boolean;
}

function createFakeListen() {
  const registrations: FakeRegistration[] = [];

  const listenFn = vi.fn(
    (eventName: string, handler: (event: { payload: unknown }) => void) => {
      const record: FakeRegistration = { eventName, handler, active: true };
      registrations.push(record);
      const unlisten: UnlistenFn = () => {
        record.active = false;
      };
      return Promise.resolve(unlisten);
    },
  );

  function byName(eventName: string): FakeRegistration {
    const reg = registrations.find((r) => r.eventName === eventName);
    if (!reg) throw new Error(`no registration for ${eventName}`);
    return reg;
  }

  function deliver(eventName: string, payload: unknown): void {
    const reg = byName(eventName);
    if (!reg.active) return;
    reg.handler({ payload });
  }

  return {
    listenFn: listenFn as unknown as (
      eventName: string,
      handler: (event: { payload: unknown }) => void,
    ) => Promise<UnlistenFn>,
    deliver,
  };
}

type FakeListen = ReturnType<typeof createFakeListen>;

async function harness() {
  const fake = createFakeListen();
  const subscription = new SidecarEventSubscription({ listenFn: fake.listenFn as never });
  const store = new SidecarProjectionStore();
  const connector = new SidecarProjectionConnector({ subscription, store });

  await subscription.start();

  return { fake, subscription, store, connector };
}

function deliverStateChanged(fake: FakeListen, overrides: Partial<StateChangedPayload> = {}): void {
  fake.deliver("sidecar:state_changed", stateChangedPayload(overrides));
}

function deliverRestartScheduled(
  fake: FakeListen,
  overrides: Partial<RestartScheduledPayload> = {},
): void {
  fake.deliver("sidecar:restart_scheduled", restartScheduledPayload(overrides));
}

function deliverRestartExhausted(
  fake: FakeListen,
  overrides: Partial<RestartExhaustedPayload> = {},
): void {
  fake.deliver("sidecar:restart_exhausted", restartExhaustedPayload(overrides));
}

// ---------------------------------------------------------------------------
// A. Event registration
// ---------------------------------------------------------------------------

describe("event registration", () => {
  it("registers exactly one onEvent() callback with the subscription", async () => {
    const { subscription, connector } = await harness();
    const onEventSpy = vi.spyOn(subscription, "onEvent");

    connector.initialize();

    expect(onEventSpy).toHaveBeenCalledTimes(1);
  });

  it("repeated initialize() does not register duplicate callbacks", async () => {
    const { subscription, connector } = await harness();
    const onEventSpy = vi.spyOn(subscription, "onEvent");

    connector.initialize();
    connector.initialize();
    connector.initialize();

    expect(onEventSpy).toHaveBeenCalledTimes(1);
  });

  it("dispose() unregisters the callback — a subsequent event has no effect", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });
    expect(store.getState()).not.toBeNull();

    connector.dispose();
    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 2 });

    expect(store.getState()?.state).toBe("STARTING");
    expect(store.getState()?.sequence).toBe(1);
  });

  it("repeated dispose() is safe", async () => {
    const { connector } = await harness();
    connector.initialize();
    expect(() => {
      connector.dispose();
      connector.dispose();
      connector.dispose();
    }).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// B. state_changed
// ---------------------------------------------------------------------------

describe("state_changed", () => {
  it("projects correctly and notifies a subscriber", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();

    const listener = vi.fn();
    store.subscribe(listener);

    deliverStateChanged(fake, {
      state: "STARTING",
      previous_state: "NOT_STARTED",
      sequence: 1,
      reason: null,
    });

    expect(store.getState()).toEqual({
      state: "STARTING",
      restart_pending: false,
      restart_pending_attempt: null,
      restart_attempts: 0,
      restart_exhausted: false,
      sequence: 1,
    });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(store.getState());
  });

  it("preserves a reason-carrying transition's lifecycle state and sequence", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });

    deliverStateChanged(fake, {
      state: "CRASHED",
      previous_state: "RUNNING",
      sequence: 2,
      reason: { code: "SIDECAR_UNEXPECTED_EXIT", message: "exited unexpectedly" },
    });

    expect(store.getState()?.state).toBe("CRASHED");
    expect(store.getState()?.sequence).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// C. restart_scheduled
// ---------------------------------------------------------------------------

describe("restart_scheduled", () => {
  it("projects correctly and notifies a subscriber", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    deliverStateChanged(fake, { state: "CRASHED", previous_state: "RUNNING", sequence: 1 });

    const listener = vi.fn();
    store.subscribe(listener);

    deliverRestartScheduled(fake, { attempt: 3, delay_ms: 4000, sequence: 2 });

    expect(store.getState()).toEqual({
      state: "CRASHED",
      restart_pending: true,
      restart_pending_attempt: 3,
      restart_attempts: 3,
      restart_exhausted: false,
      sequence: 2,
    });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("does nothing (no store state, no notification) if delivered before any state_changed event", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    const listener = vi.fn();
    store.subscribe(listener);

    deliverRestartScheduled(fake, { attempt: 1, sequence: 1 });

    expect(store.getState()).toBeNull();
    expect(listener).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// D. restart_exhausted
// ---------------------------------------------------------------------------

describe("restart_exhausted", () => {
  it("projects correctly and notifies a subscriber", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    deliverStateChanged(fake, { state: "CRASHED", previous_state: "RUNNING", sequence: 1 });
    deliverRestartScheduled(fake, { attempt: 5, sequence: 2 });

    const listener = vi.fn();
    store.subscribe(listener);

    deliverRestartExhausted(fake, { attempts: 5, sequence: 3 });

    expect(store.getState()).toEqual({
      state: "CRASHED",
      restart_pending: false,
      restart_pending_attempt: null,
      restart_attempts: 5,
      restart_exhausted: true,
      sequence: 3,
    });
    expect(listener).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// E. Sequence
// ---------------------------------------------------------------------------

describe("sequence", () => {
  it("preserves the accepted event's sequence unchanged, applied in delivery order", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();

    deliverStateChanged(fake, { state: "STARTING", sequence: 10 });
    expect(store.getState()?.sequence).toBe(10);

    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 11 });
    expect(store.getState()?.sequence).toBe(11);

    deliverRestartScheduled(fake, { attempt: 1, sequence: 12 });
    expect(store.getState()?.sequence).toBe(12);
  });

  it("a stale/duplicate sequence is dropped by Part 2D-2 and never reaches the store", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();

    deliverStateChanged(fake, { state: "STARTING", sequence: 5 });
    expect(store.getState()?.sequence).toBe(5);

    // Stale: sequence 5 already applied, sequence 3 is older.
    deliverStateChanged(fake, { state: "RUNNING", sequence: 3 });
    expect(store.getState()?.sequence).toBe(5);
    expect(store.getState()?.state).toBe("STARTING");
  });
});

// ---------------------------------------------------------------------------
// F. Notifications
// ---------------------------------------------------------------------------

describe("notifications", () => {
  it("notifies exactly once for an effective accepted event", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    const listener = vi.fn();
    store.subscribe(listener);

    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("multiple subscribers all receive the same projected state", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    const a = vi.fn();
    const b = vi.fn();
    store.subscribe(a);
    store.subscribe(b);

    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });

    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(a).toHaveBeenCalledWith(store.getState());
    expect(b).toHaveBeenCalledWith(store.getState());
  });

  it("an unsubscribed subscriber receives nothing further", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    unsubscribe();

    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });

    expect(listener).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// G. Lifecycle
// ---------------------------------------------------------------------------

describe("connector lifecycle", () => {
  it("initialize -> event -> dispose -> event: the second event does not affect the disposed connector", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });
    connector.dispose();

    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 2 });

    expect(store.getState()?.state).toBe("STARTING");
    expect(store.getState()?.sequence).toBe(1);
  });

  it("initialize -> dispose -> initialize -> event: re-initialization resumes projecting", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    connector.dispose();
    connector.initialize();

    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });

    expect(store.getState()?.state).toBe("STARTING");
    expect(store.getState()?.sequence).toBe(1);
  });

  it("getLifecycle() reflects uninitialized -> active -> disposed", async () => {
    const { connector } = await harness();
    expect(connector.getLifecycle()).toBe("uninitialized");
    connector.initialize();
    expect(connector.getLifecycle()).toBe("active");
    connector.dispose();
    expect(connector.getLifecycle()).toBe("disposed");
  });
});

// ---------------------------------------------------------------------------
// H. Multiple events
// ---------------------------------------------------------------------------

describe("multiple events", () => {
  it("state_changed -> restart_scheduled -> state_changed -> restart_exhausted: verifies projected state after each", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();

    deliverStateChanged(fake, { state: "CRASHED", previous_state: "RUNNING", sequence: 1 });
    expect(store.getState()).toMatchObject({ state: "CRASHED", sequence: 1, restart_attempts: 0 });

    deliverRestartScheduled(fake, { attempt: 1, sequence: 2 });
    expect(store.getState()).toMatchObject({
      state: "CRASHED",
      sequence: 2,
      restart_pending: true,
      restart_pending_attempt: 1,
      restart_attempts: 1,
    });

    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 3 });
    expect(store.getState()).toMatchObject({
      state: "RUNNING",
      sequence: 3,
      restart_pending: true,
      restart_attempts: 1,
    });

    deliverRestartExhausted(fake, { attempts: 5, sequence: 4 });
    expect(store.getState()).toMatchObject({
      state: "RUNNING",
      sequence: 4,
      restart_pending: false,
      restart_pending_attempt: null,
      restart_attempts: 5,
      restart_exhausted: true,
    });
  });
});

// ---------------------------------------------------------------------------
// I. Subscriber isolation
// ---------------------------------------------------------------------------

describe("subscriber isolation", () => {
  it("a throwing subscriber does not corrupt the store or block other subscribers", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();

    const throwing = vi.fn(() => {
      throw new Error("boom");
    });
    const healthy = vi.fn();
    store.subscribe(throwing);
    store.subscribe(healthy);

    expect(() => deliverStateChanged(fake, { state: "STARTING", sequence: 1 })).not.toThrow();

    expect(healthy).toHaveBeenCalledTimes(1);
    expect(store.getState()?.state).toBe("STARTING");
  });

  it("a projection failure (malformed downstream state) is logged, not thrown, and does not corrupt the store", async () => {
    const { fake, store, connector } = await harness();
    connector.initialize();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    // Force applyProjectedState to throw by disposing the store out
    // from under the connector — applyProjectedState() itself is a
    // documented no-op after dispose(), so instead we simulate a
    // thrown projection by spying on the store method.
    const applySpy = vi
      .spyOn(store, "applyProjectedState")
      .mockImplementationOnce(() => {
        throw new Error("simulated projection failure");
      });

    expect(() => deliverStateChanged(fake, { state: "STARTING", sequence: 1 })).not.toThrow();
    expect(consoleError).toHaveBeenCalled();

    applySpy.mockRestore();
    consoleError.mockRestore();

    // The connector keeps working for the next event (a fresh,
    // strictly-increasing sequence — the failed first delivery above
    // was still accepted by Part 2D-2's sequence filter even though
    // the store's own apply threw, so sequence 1 is now stale).
    deliverStateChanged(fake, { state: "STARTING", sequence: 2 });
    expect(store.getState()?.state).toBe("STARTING");
    expect(store.getState()?.sequence).toBe(2);
  });
});
