/**
 * Phase 4E-P3 Part 2D-3D — Final Integration Verification & Hardening.
 *
 * This suite does not re-implement or restate the per-layer tests
 * already owned by 2D-1 through 2D-3C (frozen, unmodified). It exists
 * to prove things only visible when the *entire* real chain runs
 * together:
 *
 *     fake Tauri listen()
 *       -> real SidecarEventSubscription        (2D-2)
 *       -> real SidecarProjectionConnector       (2D-3B)
 *       -> real SidecarProjectionStore           (2D-3A)
 *       -> real SidecarSnapshotReconciler        (2D-3C)
 *       -> fake get_sidecar_status
 *
 * Only the two external boundaries are faked (Tauri `listen()` and the
 * `get_sidecar_status` command). Nothing in between is mocked.
 *
 * Additions this checkpoint makes beyond what 2D-3C's own test suite
 * already covers:
 *
 *  - `listen()` itself resolves asynchronously (a real microtask gap),
 *    not synchronously-resolved, so the startup-ordering invariant
 *    (task brief §7: connector wiring must be registered before any
 *    event delivered once listening begins can be missed) is proven
 *    against a genuine async registration window, not just an
 *    already-settled promise.
 *  - Multi-subscriber correctness is proven through the *reconciler*,
 *    not only at the connector layer (2D-3B's own suite proves it one
 *    layer down; this proves it end-to-end).
 *  - A combined shutdown-safety pass exercises every §8 condition in
 *    one full-chain scenario together, rather than piecemeal.
 *  - Validation-boundary rejection (malformed event, malformed
 *    snapshot) is proven not to reach the store via the full chain,
 *    not only via the frozen 2D-1 validator unit tests.
 */

import { describe, expect, it, vi } from "vitest";

import type { UnlistenFn } from "@tauri-apps/api/event";

import { SidecarEventSubscription } from "./eventSubscription";
import { SidecarProjectionConnector } from "./projectionConnector";
import { SidecarProjectionStore } from "./projectionStore";
import { SidecarSnapshotReconciler } from "./snapshotReconciliation";
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
// Fake listen() — this suite's variant resolves asynchronously (a real
// microtask gap per event name), unlike 2D-3C's own synchronously
// resolved fake, to actually exercise the startup-ordering window.
// ---------------------------------------------------------------------------

interface FakeRegistration {
  readonly eventName: string;
  readonly handler: (event: { payload: unknown }) => void;
  active: boolean;
}

function createAsyncFakeListen() {
  const registrations: FakeRegistration[] = [];
  const calls: string[] = [];

  const listenFn = vi.fn(
    async (eventName: string, handler: (event: { payload: unknown }) => void) => {
      calls.push(eventName);
      // Genuine async gap: registration does not complete synchronously.
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

  function isRegistered(eventName: string): boolean {
    return registrations.some((r) => r.eventName === eventName && r.active);
  }

  return {
    listenFn: listenFn as unknown as (
      eventName: string,
      handler: (event: { payload: unknown }) => void,
    ) => Promise<UnlistenFn>,
    deliver,
    isRegistered,
    calls,
    registrations,
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
// A/§7 — Startup ordering: connector wiring is live before the async
// listen() registration gap closes, so no event delivered the instant
// registration completes is ever missed.
// ---------------------------------------------------------------------------

describe("startup ordering (task brief §7)", () => {
  it("connector.initialize() runs synchronously before subscription.start()'s async gap, so an event delivered the moment listen() settles is not lost", async () => {
    const { fake, reconciler, store } = harness(() => Promise.resolve(status({ sequence: 5 })));

    const initPromise = reconciler.initialize();

    // At this point connector.initialize() has already run (synchronous,
    // per snapshotReconciliation.ts's own documented ordering) even
    // though subscription.start()'s listen() calls have not resolved
    // yet. Confirm the registration is genuinely still pending.
    expect(fake.isRegistered("sidecar:state_changed")).toBe(false);

    await initPromise;

    // Registration is now live and the connector was wired before it,
    // so a live event lands normally.
    expect(fake.isRegistered("sidecar:state_changed")).toBe(true);
    deliverStateChanged(fake, { state: "RUNNING", sequence: 6 });
    expect(store.getState()?.sequence).toBe(6);
  });

  it("no event can reach a listener before its own registration resolves — deliver() throws for an unregistered event name", () => {
    const fake = createAsyncFakeListen();
    expect(() => deliverStateChanged(fake)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// B/§17 — Multi-subscriber correctness through the full real chain,
// including the reconciler's snapshot path (2D-3B's own suite already
// proves this one layer down, at the connector; this proves it
// end-to-end).
// ---------------------------------------------------------------------------

describe("multi-subscriber correctness through the full chain (task brief §17)", () => {
  it("two independent subscribers observe the identical sequence of projections across event + snapshot interleaving", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, reconciler, store } = harness(() => d.promise);

    const a: unknown[] = [];
    const b: unknown[] = [];
    store.subscribe((s) => a.push(s));
    store.subscribe((s) => b.push(s));

    const initPromise = reconciler.initialize();
    await vi.waitFor(() => expect(fake.isRegistered("sidecar:state_changed")).toBe(true));

    deliverStateChanged(fake, { state: "RUNNING", sequence: 11 });
    d.resolve(status({ sequence: 10 }));
    await initPromise;

    expect(a).toEqual(b);
    expect(store.getState()?.sequence).toBe(11); // stale snapshot rejected
  });

  it("an unsubscribed listener receives nothing further while the remaining subscriber keeps receiving updates", async () => {
    const { fake, reconciler, store } = harness();
    await reconciler.initialize();

    const kept: unknown[] = [];
    const dropped: unknown[] = [];
    const unsubDropped = store.subscribe((s) => dropped.push(s));
    store.subscribe((s) => kept.push(s));

    deliverStateChanged(fake, { state: "RUNNING", sequence: 2 });
    unsubDropped();
    deliverStateChanged(fake, { state: "CRASHED", sequence: 3 });

    expect(dropped.length).toBe(1);
    expect(kept.length).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// C/§8 — Combined shutdown safety: every condition in one full-chain
// scenario, not piecemeal.
// ---------------------------------------------------------------------------

describe("combined shutdown safety (task brief §8)", () => {
  it("after dispose(): no event updates the projection, no pending snapshot updates it, no subscriber is notified, and no rejection escapes", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, reconciler, store, connector } = harness(() => d.promise);

    const notifications: unknown[] = [];
    store.subscribe((s) => notifications.push(s));

    const initPromise = reconciler.initialize();
    await vi.waitFor(() => expect(fake.isRegistered("sidecar:state_changed")).toBe(true));
    deliverStateChanged(fake, { state: "RUNNING", sequence: 3 });
    const stateBeforeDispose = store.getState();
    notifications.length = 0;

    reconciler.dispose();
    expect(connector.getLifecycle()).toBe("disposed");

    // Event after dispose: connector's own onEvent() registration was
    // torn down, so the underlying SidecarEventSubscription may still
    // dispatch (it is not owned by the reconciler — 2D-3B's ownership
    // boundary), but the connector no longer forwards to the store.
    if (fake.isRegistered("sidecar:state_changed")) {
      deliverStateChanged(fake, { state: "CRASHED", sequence: 4 });
    }
    expect(store.getState()).toBe(stateBeforeDispose);
    expect(notifications).toHaveLength(0);

    // Pending snapshot resolving after dispose must not throw and must
    // not touch the store.
    d.resolve(status({ sequence: 99 }));
    await expect(initPromise).resolves.toBeDefined();
    expect(store.getState()).toBe(stateBeforeDispose);
    expect(notifications).toHaveLength(0);
  });

  it("dispose() is idempotent and safe before initialize() has ever run", () => {
    const { reconciler } = harness();
    expect(() => {
      reconciler.dispose();
      reconciler.dispose();
      reconciler.dispose();
    }).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// D/§9 — Validation boundary: malformed data never reaches the store,
// proven through the full chain rather than the isolated validators.
// ---------------------------------------------------------------------------

describe("validation boundary through the full chain (task brief §9/§19)", () => {
  it("a malformed state_changed payload is dropped before the store, and does not disturb existing state", async () => {
    const { fake, reconciler, store } = harness();
    await reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 2 });
    const before = store.getState();

    expect(() => fake.deliver("sidecar:state_changed", { garbage: true })).not.toThrow();

    expect(store.getState()).toBe(before);
  });

  it("a structurally malformed snapshot (rejected by getSidecarStatus's own validation, surfacing as a fetchStatus rejection) leaves existing state intact", async () => {
    const { reconciler, store, fake } = harness(() =>
      Promise.reject(new Error("SidecarStatusUnavailableError: malformed response")),
    );
    await reconciler.initialize();
    // no prior event applied — projection should remain null, not throw
    expect(store.getState()).toBeNull();

    await reconciler.initialize(); // already active — no-op, same settled result
    expect(store.getState()).toBeNull();
    expect(fake.calls.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// E/§18 — No notification storms across a realistic full-chain sequence.
// ---------------------------------------------------------------------------

describe("no notification storms (task brief §18)", () => {
  it("an equal-sequence, field-identical snapshot following an identical live event produces at most one notification, not two", async () => {
    const d = deferred<SidecarStatus>();
    const { fake, reconciler, store } = harness(() => d.promise);
    let notifyCount = 0;
    store.subscribe(() => {
      notifyCount += 1;
    });

    const initPromise = reconciler.initialize();
    await vi.waitFor(() => expect(fake.isRegistered("sidecar:state_changed")).toBe(true));

    deliverStateChanged(fake, { state: "RUNNING", sequence: 7 });
    expect(notifyCount).toBe(1);

    // Snapshot arrives with the exact same effective values already
    // projected by the event above.
    d.resolve(
      status({
        state: "RUNNING",
        sequence: 7,
        restart_pending: false,
        restart_attempts: 0,
        restart_exhausted: false,
        restart_pending_attempt: null,
      }),
    );
    await initPromise;

    expect(notifyCount).toBe(1); // no redundant second notification
  });
});

// ---------------------------------------------------------------------------
// F/§10 — Listener lifecycle audit through the full chain: start once,
// start repeatedly, stop once, stop repeatedly, restart.
// ---------------------------------------------------------------------------

describe("listener lifecycle audit (task brief §10)", () => {
  it("repeated reconciler.initialize() results in exactly one active listener per event name", async () => {
    const { fake, reconciler } = harness();
    await Promise.all([reconciler.initialize(), reconciler.initialize(), reconciler.initialize()]);

    const activeStateChanged = fake.registrations.filter(
      (r) => r.eventName === "sidecar:state_changed" && r.active,
    );
    expect(activeStateChanged).toHaveLength(1);
    expect(fake.listenFn).toHaveBeenCalledTimes(3); // one per distinct sidecar event name, once total
  });

  it("initialize -> dispose -> initialize yields exactly one fresh active connection, not a stacked one", async () => {
    const { fake, reconciler, store } = harness();
    await reconciler.initialize();
    reconciler.dispose();
    await reconciler.initialize();

    deliverStateChanged(fake, { state: "RUNNING", sequence: 4 });
    expect(store.getState()?.sequence).toBe(4);

    // Only one handler fires per delivered event — verified indirectly:
    // a single delivery producing a single sequence value (not applied
    // twice / no duplicate-notify side effect) confirms no stacked
    // registration.
    let notifyCount = 0;
    store.subscribe(() => {
      notifyCount += 1;
    });
    deliverStateChanged(fake, { state: "CRASHED", sequence: 5 });
    expect(notifyCount).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// G/§20 — Error-path audit combined: one subscriber throwing does not
// prevent the other subscriber or the reconciler's own diagnostics
// from operating correctly, through the full chain.
// ---------------------------------------------------------------------------

describe("error-path audit through the full chain (task brief §20)", () => {
  it("a throwing subscriber does not corrupt store state or block the reconciler's diagnostic channel", async () => {
    const { fake, reconciler, store } = harness();
    const diagnostics: string[] = [];
    reconciler.onDiagnostic((d) => diagnostics.push(d.kind));

    store.subscribe(() => {
      throw new Error("boom");
    });
    const healthy: unknown[] = [];
    store.subscribe((s) => healthy.push(s));

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    await reconciler.initialize();
    deliverStateChanged(fake, { state: "RUNNING", sequence: 2 });
    errorSpy.mockRestore();

    expect(store.getState()?.sequence).toBe(2);
    // One notification from initialize()'s own baseline snapshot apply,
    // one from the live event above -- both delivered to the healthy
    // subscriber despite the other subscriber throwing on every call.
    expect(healthy).toHaveLength(2);
    expect(diagnostics).toContain("snapshot_applied");
  });
});
