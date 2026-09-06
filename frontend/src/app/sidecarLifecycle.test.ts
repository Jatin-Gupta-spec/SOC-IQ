/**
 * Phase 4G Implementation Part 1 — composition-root lifecycle
 * integration tests.
 *
 * Mirrors `shared/sidecar/finalIntegration.test.ts`'s own harness
 * approach exactly: only the two external boundaries (Tauri
 * `listen()` and the `get_sidecar_status` command) are faked. Every
 * other layer — `SidecarEventSubscription`, `SidecarProjectionConnector`,
 * `SidecarProjectionStore`, `SidecarSnapshotReconciler` — is the real,
 * frozen Part 2D class, wired together exactly as
 * `snapshotReconciliation.ts`'s own default singleton wires them.
 * `startSidecarLifecycle`/`stop` (this checkpoint's only new
 * production code) is exercised directly, with no React rendering
 * involved, per this project's existing test conventions (no
 * React-rendering test dependency exists elsewhere in this repo).
 *
 * Proves the actual ownership chain:
 *
 *     startSidecarLifecycle()
 *       -> SidecarSnapshotReconciler   (2D-3C, frozen)
 *       -> SidecarEventSubscription    (2D-2, frozen)
 *       -> SidecarProjectionConnector  (2D-3B, frozen)
 *       -> SidecarProjectionStore      (2D-3A, frozen)
 */

import { describe, expect, it, vi } from "vitest";

import type { UnlistenFn } from "@tauri-apps/api/event";

import { SidecarEventSubscription } from "../shared/sidecar/eventSubscription";
import { SidecarProjectionConnector } from "../shared/sidecar/projectionConnector";
import { SidecarProjectionStore } from "../shared/sidecar/projectionStore";
import { SidecarSnapshotReconciler } from "../shared/sidecar/snapshotReconciliation";
import type { SidecarStatus, StateChangedPayload } from "../shared/sidecar/types";
import { startSidecarLifecycle } from "./sidecarLifecycle";

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
// Same fake listen() shape as finalIntegration.test.ts — a genuine async
// registration gap, not synchronously resolved.
// ---------------------------------------------------------------------------

interface FakeRegistration {
  readonly eventName: string;
  readonly handler: (event: { payload: unknown }) => void;
  active: boolean;
}

function createAsyncFakeListen() {
  const registrations: FakeRegistration[] = [];

  const listenFn = vi.fn(
    async (eventName: string, handler: (event: { payload: unknown }) => void) => {
      await Promise.resolve();
      await Promise.resolve();
      const record: FakeRegistration = { eventName, handler, active: true };
      registrations.push(record);
      const unlisten: UnlistenFn = () => {
        record.active = false;
      };
      return unlisten;
    },
  );

  function deliver(eventName: string, payload: unknown): void {
    const reg = registrations.find((r) => r.eventName === eventName && r.active);
    if (!reg) throw new Error(`no active registration for ${eventName}`);
    reg.handler({ payload });
  }

  function activeCount(eventName: string): number {
    return registrations.filter((r) => r.eventName === eventName && r.active).length;
  }

  return {
    listenFn: listenFn as unknown as (
      eventName: string,
      handler: (event: { payload: unknown }) => void,
    ) => Promise<UnlistenFn>,
    deliver,
    activeCount,
    listenFn_: listenFn,
  };
}

type FakeListen = ReturnType<typeof createAsyncFakeListen>;

function deliverStateChanged(
  fake: FakeListen,
  overrides: Partial<StateChangedPayload> = {},
): void {
  fake.deliver("sidecar:state_changed", stateChangedPayload(overrides));
}

function harness(fetchStatus?: () => Promise<SidecarStatus>) {
  const fake = createAsyncFakeListen();
  const subscription = new SidecarEventSubscription({ listenFn: fake.listenFn as never });
  const store = new SidecarProjectionStore();
  const connector = new SidecarProjectionConnector({ subscription, store });
  const fetchStatusFn = fetchStatus ?? vi.fn(() => Promise.resolve(status()));
  const reconciler = new SidecarSnapshotReconciler({
    connector,
    store,
    subscription,
    fetchStatus: fetchStatusFn,
  });
  return { fake, subscription, store, connector, fetchStatus: fetchStatusFn, reconciler };
}

// ---------------------------------------------------------------------------
// Test A — startup
// ---------------------------------------------------------------------------

describe("Test A — startup", () => {
  it("starting the lifecycle initializes the real chain: subscription registers, snapshot applies to the store", async () => {
    const { fake, store, reconciler } = harness(() =>
      Promise.resolve(status({ sequence: 3 })),
    );

    startSidecarLifecycle(reconciler);
    await reconciler.initialize();

    expect(fake.activeCount("sidecar:state_changed")).toBe(1);
    expect(store.getState()?.sequence).toBe(3);

    // Live events keep flowing through the same real chain afterwards.
    deliverStateChanged(fake, { state: "RUNNING", sequence: 4 });
    expect(store.getState()?.sequence).toBe(4);
  });
});

// ---------------------------------------------------------------------------
// Test B — duplicate startup
// ---------------------------------------------------------------------------

describe("Test B — duplicate startup", () => {
  it("calling startSidecarLifecycle's underlying reconciler twice does not double-register the listener", async () => {
    const { fake, reconciler } = harness();

    const owner = startSidecarLifecycle(reconciler);
    // A second, independent owner over the SAME reconciler instance —
    // exactly the scenario a second accidental composition-root call
    // would create.
    startSidecarLifecycle(reconciler);

    await reconciler.initialize();

    expect(fake.activeCount("sidecar:state_changed")).toBe(1);
    // Exactly one `listen()` call per distinct sidecar event name
    // (state_changed, restart_scheduled, restart_exhausted) — not one
    // per `startSidecarLifecycle()` call. A duplicate-listener bug
    // would double this count.
    const names = fake.listenFn_.mock.calls.map((call) => call[0]);
    expect(names).toHaveLength(3);
    expect(new Set(names).size).toBe(3);

    owner.stop();
  });
});

// ---------------------------------------------------------------------------
// Test C — shutdown
// ---------------------------------------------------------------------------

describe("Test C — shutdown", () => {
  it("stopping the lifecycle disposes the connector registration; further events are not applied", async () => {
    const { fake, store, reconciler } = harness();

    const owner = startSidecarLifecycle(reconciler);
    await reconciler.initialize();

    deliverStateChanged(fake, { state: "RUNNING", sequence: 2 });
    expect(store.getState()?.sequence).toBe(2);

    owner.stop();
    expect(reconciler.getLifecycle()).toBe("disposed");

    // The connector is disposed; a further delivered event must not
    // reach the store (proves real disposal, not merely a flag).
    deliverStateChanged(fake, { state: "RUNNING", sequence: 3 });
    expect(store.getState()?.sequence).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Test D — shutdown during initialization
// ---------------------------------------------------------------------------

describe("Test D — shutdown during initialization", () => {
  it("stopping while initialize() is still in flight prevents the pending snapshot from ever reaching the store", async () => {
    const gate = deferred<SidecarStatus>();
    const { store, reconciler } = harness(() => gate.promise);

    const owner = startSidecarLifecycle(reconciler);

    // Give the subscription's async listen() registration a chance to
    // start, but do not let the snapshot fetch resolve yet.
    await Promise.resolve();
    await Promise.resolve();

    owner.stop();
    expect(reconciler.getLifecycle()).toBe("disposed");

    // Now let the in-flight snapshot resolve — it must be discarded
    // as superseded, per the frozen reconciler's own generation guard.
    gate.resolve(status({ sequence: 9 }));
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(store.getState()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Test E — restart
// ---------------------------------------------------------------------------

describe("Test E — restart", () => {
  it("initialize -> dispose -> initialize (via stop + start again) yields exactly one fresh active connection", async () => {
    const { fake, store, reconciler } = harness(() =>
      Promise.resolve(status({ sequence: 1 })),
    );

    const first = startSidecarLifecycle(reconciler);
    await reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 2 });
    expect(store.getState()?.sequence).toBe(2);

    first.stop();
    expect(reconciler.getLifecycle()).toBe("disposed");

    // The reconciler's own connector registration is torn down; a
    // live event delivered while disposed must not reach the store.
    // (The underlying Tauri `listen()` itself is intentionally left
    // running — that belongs to `SidecarEventSubscription`, not this
    // reconciler; see `projectionConnector.ts`'s ownership-boundary
    // doc comment. This is why the assertion is "did the store
    // change", not "is listen() still registered".)
    deliverStateChanged(fake, { state: "RUNNING", sequence: 3 });
    expect(store.getState()?.sequence).toBe(2);

    const second = startSidecarLifecycle(reconciler);
    await reconciler.initialize();
    expect(reconciler.getLifecycle()).toBe("active");

    // Exactly one fresh connection: one delivered event updates the
    // store exactly once, never duplicated by a stacked registration
    // left over from the first lifecycle.
    deliverStateChanged(fake, { state: "RUNNING", sequence: 4 });
    expect(store.getState()?.sequence).toBe(4);

    second.stop();
  });
});

// ---------------------------------------------------------------------------
// Test F — startup failure
// ---------------------------------------------------------------------------

describe("Test F — startup failure", () => {
  it("a rejected snapshot fetch is logged, does not throw past startSidecarLifecycle, and leaves the reconciler active/coherent", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const failure = new Error("boom: snapshot unavailable");
    const { store, reconciler } = harness(() => Promise.reject(failure));

    let thrown: unknown;
    try {
      startSidecarLifecycle(reconciler);
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeUndefined();

    await reconciler.initialize();

    expect(reconciler.getLifecycle()).toBe("active");
    expect(store.getState()).toBeNull();
    expect(consoleError).toHaveBeenCalledWith(
      "SOC-IQ: sidecar snapshot fetch failed during startup",
      failure,
    );

    consoleError.mockRestore();
  });

  it("the application remains shut-down-safe after a startup failure", async () => {
    const { reconciler } = harness(() => Promise.reject(new Error("boom")));
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const owner = startSidecarLifecycle(reconciler);
    await reconciler.initialize();

    expect(() => owner.stop()).not.toThrow();
    expect(reconciler.getLifecycle()).toBe("disposed");

    vi.restoreAllMocks();
  });
});
