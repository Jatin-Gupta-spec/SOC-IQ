/**
 * Tests for the Phase 4E-P3 Part 2D-3C snapshot integration /
 * reconciliation / race-handling layer (`snapshotReconciliation.ts`).
 *
 * Per task brief §28: the integration tests below exercise the
 * complete real pipeline --
 *
 *     fake Tauri listen()
 *       -> real SidecarEventSubscription (Part 2D-2)
 *       -> real SidecarProjectionConnector (Part 2D-3B)
 *       -> real SidecarProjectionStore (Part 2D-3A)
 *       -> real SidecarSnapshotReconciler (Part 2D-3C, this checkpoint)
 *
 * -- with only two external boundaries faked: the Tauri `listen()`
 * call (the same `listenFn` injection seam every other sidecar test
 * suite already uses) and the `get_sidecar_status` call itself (via
 * `fetchStatus`, this reconciler's own injection seam -- analogous to
 * `SidecarProjectionConnector`'s `subscription`/`store` injection).
 * Nothing here mocks the projection store or replaces the event
 * projection pipeline with a fake.
 *
 * The pure `reconcileSnapshot()` matrix (task brief §25's eight
 * documented cases) is additionally tested directly against the real
 * exported function, independent of any class.
 */

import { describe, expect, it, vi } from "vitest";

import type { UnlistenFn } from "@tauri-apps/api/event";

import { SidecarEventSubscription } from "./eventSubscription";
import { SidecarProjectionConnector } from "./projectionConnector";
import { SidecarProjectionStore } from "./projectionStore";
import {
  SidecarSnapshotReconciler,
  reconcileSnapshot,
} from "./snapshotReconciliation";
import type { SidecarStatus, StateChangedPayload } from "./types";

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

// ---------------------------------------------------------------------------
// Fake listen() -- the one Tauri-event boundary this suite fakes.
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

  function deliver(eventName: string, payload: unknown): void {
    const reg = registrations.find((r) => r.eventName === eventName && r.active);
    if (!reg) throw new Error(`no active registration for ${eventName}`);
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

function deliverStateChanged(
  fake: FakeListen,
  overrides: Partial<StateChangedPayload> = {},
): void {
  fake.deliver("sidecar:state_changed", stateChangedPayload(overrides));
}

// ---------------------------------------------------------------------------
// Harness -- the real pipeline, only listen()/get_sidecar_status faked.
// ---------------------------------------------------------------------------

function harness(fetchStatus?: () => Promise<SidecarStatus>) {
  const fake = createFakeListen();
  const subscription = new SidecarEventSubscription({ listenFn: fake.listenFn as never });
  const store = new SidecarProjectionStore();
  const connector = new SidecarProjectionConnector({ subscription, store });
  const fetch = fetchStatus ?? vi.fn(() => Promise.resolve(status()));
  const reconciler = new SidecarSnapshotReconciler({
    connector,
    store,
    subscription,
    fetchStatus: fetch,
  });
  return { fake, subscription, store, connector, fetchStatus: fetch, reconciler };
}

// ---------------------------------------------------------------------------
// A. reconcileSnapshot() pure algorithm -- task brief §25's 8 cases
// ---------------------------------------------------------------------------

describe("reconcileSnapshot() — task brief §25 ordering matrix", () => {
  it("Case 1: snapshot 10 establishes baseline when nothing projected yet", () => {
    const result = reconcileSnapshot(null, status({ sequence: 10, state: "STARTING" }));
    expect(result).toEqual(status({ sequence: 10, state: "STARTING" }));
  });

  it("Case 2: event 11 -> snapshot 10 is rejected (stale)", () => {
    const current = status({ sequence: 11, state: "RUNNING" });
    const result = reconcileSnapshot(current, status({ sequence: 10, state: "STARTING" }));
    expect(result).toBeNull();
  });

  it("Case 3: event 10 -> snapshot 11 is applied (newer)", () => {
    const current = status({ sequence: 10, state: "STARTING" });
    const result = reconcileSnapshot(current, status({ sequence: 11, state: "RUNNING" }));
    expect(result?.sequence).toBe(11);
    expect(result?.state).toBe("RUNNING");
  });

  it("Case 4: event 10 -> snapshot 10 (equal) is applied — corrects restart-accounting without changing sequence", () => {
    const current = status({ sequence: 10, restart_pending: false, restart_attempts: 0 });
    const snapshot = status({
      sequence: 10,
      restart_pending: true,
      restart_pending_attempt: 3,
      restart_attempts: 3,
    });
    const result = reconcileSnapshot(current, snapshot);
    expect(result).toEqual(snapshot);
    expect(result?.sequence).toBe(current.sequence);
  });

  it("Case 5: event 11 -> event 12 -> snapshot 10 is rejected, stays 12", () => {
    const current = status({ sequence: 12 });
    const result = reconcileSnapshot(current, status({ sequence: 10 }));
    expect(result).toBeNull();
  });

  it("Case 6: snapshot 10 -> event 11 -> event 12 -> snapshot 9 is rejected, stays 12", () => {
    const afterFirstSnapshot = reconcileSnapshot(null, status({ sequence: 10 }))!;
    const afterEvents: SidecarStatus = { ...afterFirstSnapshot, sequence: 12 };
    const result = reconcileSnapshot(afterEvents, status({ sequence: 9 }));
    expect(result).toBeNull();
  });

  it("Case 7: snapshot pending -> event 11 -> snapshot 11 is applied (equal, no rollback)", () => {
    const current = status({ sequence: 11 });
    const result = reconcileSnapshot(current, status({ sequence: 11 }));
    expect(result?.sequence).toBe(11);
  });

  it("Case 8: snapshot pending -> event 11,12,13 -> snapshot 10 is rejected, stays 13", () => {
    const current = status({ sequence: 13 });
    const result = reconcileSnapshot(current, status({ sequence: 10 }));
    expect(result).toBeNull();
  });

  it("never mutates its inputs", () => {
    const current = status({ sequence: 5 });
    const frozenCurrent = Object.freeze({ ...current });
    const snapshot = Object.freeze(status({ sequence: 6 }));
    expect(() => reconcileSnapshot(frozenCurrent, snapshot)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// B. Full-stack race scenarios via the coordinator
// ---------------------------------------------------------------------------

describe("full-stack races", () => {
  it("event-before-snapshot: event 11 arrives while snapshot is pending, snapshot 10 resolves after -> final sequence stays 11", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 11 });
    expect(store.getState()?.sequence).toBe(11);

    d.resolve(status({ sequence: 10, state: "STARTING" }));
    const outcome = await initPromise;

    expect(outcome.kind).toBe("stale");
    expect(store.getState()?.sequence).toBe(11);
    expect(store.getState()?.state).toBe("RUNNING");
  });

  it("snapshot-before-event: snapshot 10 applied first, then event 11 advances normally -> final sequence 11", async () => {
    const { fake, store, reconciler } = harness(() =>
      Promise.resolve(status({ sequence: 10, state: "STARTING" })),
    );

    const outcome = await reconciler.initialize();
    expect(outcome.kind).toBe("applied");
    expect(store.getState()?.sequence).toBe(10);

    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 11 });
    expect(store.getState()?.sequence).toBe(11);
  });

  it("multiple events during a pending snapshot: 11, 12, 13 all land before snapshot 10 resolves -> final sequence stays 13", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 11 });
    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 12 });
    deliverStateChanged(fake, { state: "CRASHED", previous_state: "RUNNING", sequence: 13 });
    expect(store.getState()?.sequence).toBe(13);

    d.resolve(status({ sequence: 10, state: "STARTING" }));
    const outcome = await initPromise;

    expect(outcome.kind).toBe("stale");
    expect(store.getState()?.sequence).toBe(13);
    expect(store.getState()?.state).toBe("CRASHED");
  });

  it("snapshot newer than existing event becomes authoritative", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 10 });
    expect(store.getState()?.sequence).toBe(10);

    d.resolve(status({ sequence: 11, state: "RUNNING", restart_attempts: 2 }));
    const outcome = await initPromise;

    expect(outcome.kind).toBe("applied");
    expect(store.getState()?.sequence).toBe(11);
    expect(store.getState()?.state).toBe("RUNNING");
    expect(store.getState()?.restart_attempts).toBe(2);
  });

  it("establishes the very first projection purely from the snapshot when no event has ever arrived", async () => {
    const { store, reconciler } = harness(() =>
      Promise.resolve(
        status({ sequence: 4, state: "RUNNING", restart_attempts: 1, restart_pending: true, restart_pending_attempt: 1 }),
      ),
    );

    expect(store.getState()).toBeNull();
    const outcome = await reconciler.initialize();

    expect(outcome.kind).toBe("applied");
    expect(store.getState()).toEqual(
      status({ sequence: 4, state: "RUNNING", restart_attempts: 1, restart_pending: true, restart_pending_attempt: 1 }),
    );
  });
});

// ---------------------------------------------------------------------------
// C. Restart-accounting correction (task brief §26)
// ---------------------------------------------------------------------------

describe("restart-accounting correction", () => {
  it("corrects stale event-derived restart_pending once the snapshot reconciles at equal sequence", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "CRASHED", sequence: 5 });
    // Event-only projection cannot know a scheduled restart already
    // fired (eventProjection.ts's own documented gap) — a
    // restart_scheduled event leaves restart_pending stuck `true`
    // until the *next* event, which may not arrive for a while.
    fake.deliver("sidecar:restart_scheduled", {
      attempt: 2,
      delay_ms: 500,
      sequence: 6,
      timestamp: TIMESTAMP,
    });
    expect(store.getState()).toMatchObject({
      sequence: 6,
      restart_pending: true,
      restart_pending_attempt: 2,
      restart_attempts: 2,
    });

    // The backend-authoritative snapshot, read at the same sequence,
    // already reflects that the restart fired and is no longer
    // pending — exactly the correction task brief §23 describes.
    d.resolve(
      status({
        sequence: 6,
        state: "CRASHED",
        restart_pending: false,
        restart_pending_attempt: null,
        restart_attempts: 2,
        restart_exhausted: false,
      }),
    );
    const outcome = await initPromise;

    expect(outcome.kind).toBe("applied");
    expect(store.getState()?.sequence).toBe(6);
    expect(store.getState()?.restart_pending).toBe(false);
    expect(store.getState()?.restart_pending_attempt).toBeNull();
    expect(store.getState()?.restart_attempts).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// D. Failure handling (task brief §17/§27)
// ---------------------------------------------------------------------------

describe("snapshot failure", () => {
  it("a rejected fetchStatus() does not destroy valid existing projected state", async () => {
    const { fake, store, reconciler } = harness(() => Promise.reject(new Error("IPC failure")));

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 1 });
    expect(store.getState()?.sequence).toBe(1);

    const outcome = await initPromise;

    expect(outcome.kind).toBe("failed");
    expect(store.getState()?.sequence).toBe(1);
    expect(store.getState()?.state).toBe("RUNNING");
  });

  it("initialize() never rejects, even when the snapshot fetch fails", async () => {
    const { reconciler } = harness(() => Promise.reject(new Error("boom")));
    await expect(reconciler.initialize()).resolves.toMatchObject({ kind: "failed" });
  });

  it("initialization lifecycle reaches 'active' after a snapshot failure, not stuck in 'initializing'", async () => {
    const { reconciler } = harness(() => Promise.reject(new Error("boom")));
    await reconciler.initialize();
    expect(reconciler.getLifecycle()).toBe("active");
  });

  it("live events continue projecting normally after a snapshot failure", async () => {
    const { fake, store, reconciler } = harness(() => Promise.reject(new Error("boom")));
    await reconciler.initialize();

    deliverStateChanged(fake, { state: "STARTING", sequence: 1 });
    expect(store.getState()?.sequence).toBe(1);
    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 2 });
    expect(store.getState()?.sequence).toBe(2);
  });

  it("emits a snapshot_fetch_failed diagnostic", async () => {
    const error = new Error("boom");
    const { reconciler } = harness(() => Promise.reject(error));
    const diagnostic = vi.fn();
    reconciler.onDiagnostic(diagnostic);

    await reconciler.initialize();

    expect(diagnostic).toHaveBeenCalledWith({ kind: "snapshot_fetch_failed", error });
  });
});

// ---------------------------------------------------------------------------
// E. Lifecycle: repeated initialize, disposal, reinitialization, staleness
// ---------------------------------------------------------------------------

describe("lifecycle", () => {
  it("repeated initialize() while in flight returns the same promise and calls fetchStatus only once", async () => {
    const d = deferred<SidecarStatus>();
    const fetchStatus = vi.fn(() => d.promise);
    const { reconciler } = harness(fetchStatus);

    const p1 = reconciler.initialize();
    const p2 = reconciler.initialize();
    const p3 = reconciler.initialize();
    expect(p1).toBe(p2);
    expect(p2).toBe(p3);

    d.resolve(status({ sequence: 1 }));
    await p1;

    expect(fetchStatus).toHaveBeenCalledTimes(1);
  });

  it("repeated initialize() after completion (active) also returns the settled promise, no second fetch", async () => {
    const fetchStatus = vi.fn(() => Promise.resolve(status({ sequence: 1 })));
    const { reconciler } = harness(fetchStatus);

    await reconciler.initialize();
    await reconciler.initialize();
    await reconciler.initialize();

    expect(fetchStatus).toHaveBeenCalledTimes(1);
  });

  it("does not register duplicate event subscriptions across repeated initialize()", async () => {
    const { subscription, reconciler } = harness(() => Promise.resolve(status({ sequence: 1 })));
    const onEventSpy = vi.spyOn(subscription, "onEvent");

    await reconciler.initialize();
    await reconciler.initialize();

    expect(onEventSpy).toHaveBeenCalledTimes(1);
  });

  it("dispose() is safe to call repeatedly, including before initialize()", () => {
    const { reconciler } = harness();
    expect(() => {
      reconciler.dispose();
      reconciler.dispose();
      reconciler.dispose();
    }).not.toThrow();
    expect(reconciler.getLifecycle()).toBe("disposed");
  });

  it("dispose() after initialize() stops further events from projecting", async () => {
    const { fake, store, reconciler } = harness(() => Promise.resolve(status({ sequence: 1 })));
    await reconciler.initialize();
    deliverStateChanged(fake, { state: "STARTING", sequence: 2 });
    expect(store.getState()?.sequence).toBe(2);

    reconciler.dispose();
    deliverStateChanged(fake, { state: "RUNNING", previous_state: "STARTING", sequence: 3 });

    expect(store.getState()?.sequence).toBe(2);
  });

  it("initialize() -> dispose() -> initialize() resumes projecting (deterministic reinitialization)", async () => {
    const { fake, store, reconciler } = harness(() => Promise.resolve(status({ sequence: 1 })));
    await reconciler.initialize();
    reconciler.dispose();
    await reconciler.initialize();

    deliverStateChanged(fake, { state: "RUNNING", sequence: 5 });
    expect(store.getState()?.sequence).toBe(5);
  });

  it("a stale snapshot resolving after dispose() does not corrupt the store (generation guard)", async () => {
    const d = deferred<SidecarStatus>();
    const { store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    reconciler.dispose();
    d.resolve(status({ sequence: 99, state: "RUNNING" }));
    const outcome = await initPromise;

    expect(outcome.kind).toBe("superseded");
    expect(store.getState()).toBeNull();
  });

  it("initialize A pending -> dispose -> initialize B resolves -> stale snapshot A resolves later: A must not corrupt B's lifecycle", async () => {
    const dA = deferred<SidecarStatus>();
    const dB = deferred<SidecarStatus>();
    let call = 0;
    const fetchStatus = vi.fn(() => (call++ === 0 ? dA.promise : dB.promise));
    const { store, reconciler } = harness(fetchStatus);

    const initA = reconciler.initialize();
    reconciler.dispose();
    const initB = reconciler.initialize();

    dB.resolve(status({ sequence: 7, state: "RUNNING" }));
    const outcomeB = await initB;
    expect(outcomeB.kind).toBe("applied");
    expect(store.getState()?.sequence).toBe(7);

    // Snapshot A resolves after B has already been applied — must be
    // discarded, not overwrite B's result.
    dA.resolve(status({ sequence: 1, state: "STARTING" }));
    const outcomeA = await initA;
    expect(outcomeA.kind).toBe("superseded");
    expect(store.getState()?.sequence).toBe(7);
    expect(store.getState()?.state).toBe("RUNNING");
  });

  it("getLifecycle() reflects uninitialized -> initializing -> active -> disposed", async () => {
    const d = deferred<SidecarStatus>();
    const { reconciler } = harness(() => d.promise);

    expect(reconciler.getLifecycle()).toBe("uninitialized");
    const initPromise = reconciler.initialize();
    expect(reconciler.getLifecycle()).toBe("initializing");

    d.resolve(status({ sequence: 1 }));
    await initPromise;
    expect(reconciler.getLifecycle()).toBe("active");

    reconciler.dispose();
    expect(reconciler.getLifecycle()).toBe("disposed");
  });
});

// ---------------------------------------------------------------------------
// F. Notification behavior (task brief §24)
// ---------------------------------------------------------------------------

describe("notification behavior", () => {
  it("does not notify subscribers for a stale (rejected) snapshot", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 5 });

    const listener = vi.fn();
    store.subscribe(listener);

    d.resolve(status({ sequence: 3, state: "STARTING" }));
    await initPromise;

    expect(listener).not.toHaveBeenCalled();
  });

  it("does not notify subscribers for a failed snapshot fetch", async () => {
    const { store, reconciler } = harness(() => Promise.reject(new Error("boom")));
    const listener = vi.fn();
    store.subscribe(listener);

    await reconciler.initialize();

    expect(listener).not.toHaveBeenCalled();
  });

  it("does not notify subscribers when an equal-sequence snapshot changes nothing", async () => {
    // The store is pre-seeded with exactly what the snapshot will say
    // (via a real event) before the snapshot resolves, so applying it
    // is a byte-for-byte no-op.
    const d = deferred<SidecarStatus>();
    const { fake, store, reconciler } = harness(() => d.promise);

    const initPromise = reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 5 });

    const listener = vi.fn();
    store.subscribe(listener);

    d.resolve(status({ sequence: 5, state: "RUNNING" }));
    const outcome = await initPromise;

    expect(outcome.kind).toBe("applied");
    expect(listener).not.toHaveBeenCalled();
  });

  it("notifies exactly once for an accepted, state-changing snapshot", async () => {
    const { store, reconciler } = harness(() =>
      Promise.resolve(status({ sequence: 1, state: "RUNNING" })),
    );
    const listener = vi.fn();
    store.subscribe(listener);

    await reconciler.initialize();

    expect(listener).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// G. Malformed / invalid snapshot from the API layer (task brief §16/§27)
// ---------------------------------------------------------------------------

describe("malformed snapshot rejection propagates from the API layer", () => {
  it("a fetchStatus() rejection (as getSidecarStatus() produces for malformed data) resolves as 'failed', never applied", async () => {
    const { store, reconciler } = harness(() =>
      Promise.reject(new Error("the response did not match the SidecarStatus contract")),
    );

    const outcome = await reconciler.initialize();

    expect(outcome.kind).toBe("failed");
    expect(store.getState()).toBeNull();
  });
});
