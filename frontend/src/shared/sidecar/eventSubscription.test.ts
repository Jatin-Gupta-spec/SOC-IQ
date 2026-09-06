/**
 * Tests for the Phase 4E-P3 Part 2D-2 real Tauri `listen()`
 * subscription layer (`eventSubscription.ts`).
 *
 * Per task brief §14: "Mock the Tauri event API at the infrastructure
 * boundary. Do not mock your own subscription service." — these tests
 * never `vi.mock("@tauri-apps/api/event")`. Instead they construct a
 * fresh `SidecarEventSubscription` per test with a controlled fake
 * `listenFn` injected through the constructor's own
 * `SidecarEventSubscriptionOptions` (the seam the production class
 * already exposes for exactly this purpose), matching
 * `client.test.ts`'s "mock the transport boundary, not the module
 * under test" convention.
 *
 * The fake `listenFn` below is deliberately asynchronous (returns a
 * pending promise until a test explicitly resolves/rejects it) so
 * that the async-registration-race tests (§10/§13's "async lifecycle
 * races") can exercise `start()`/`stop()` interleavings against a
 * real microtask gap, not just against an already-settled promise.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { UnlistenFn } from "@tauri-apps/api/event";

import {
  EVENT_RESTART_EXHAUSTED,
  EVENT_RESTART_SCHEDULED,
  EVENT_STATE_CHANGED,
  type RestartExhaustedPayload,
  type RestartScheduledPayload,
  type StateChangedPayload,
} from "./types";
import {
  SidecarEventSubscription,
  type SidecarDiagnostic,
  type SidecarDomainEvent,
} from "./eventSubscription";

const VALID_TIMESTAMP = "2026-08-25T09:47:00Z";

// ---------------------------------------------------------------------------
// Valid payload builders
// ---------------------------------------------------------------------------

function stateChangedPayload(
  overrides: Partial<StateChangedPayload> = {},
): StateChangedPayload {
  return {
    state: "RUNNING",
    previous_state: "STARTING",
    reason: null,
    sequence: 1,
    generation: 1,
    timestamp: VALID_TIMESTAMP,
    ...overrides,
  };
}

function restartScheduledPayload(
  overrides: Partial<RestartScheduledPayload> = {},
): RestartScheduledPayload {
  return {
    attempt: 1,
    delay_ms: 500,
    sequence: 1,
    timestamp: VALID_TIMESTAMP,
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
    timestamp: VALID_TIMESTAMP,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Fake listen() — the infrastructure boundary
// ---------------------------------------------------------------------------

interface FakeRegistration {
  readonly eventName: string;
  readonly handler: (event: { payload: unknown }) => void;
  readonly unlistenMock: ReturnType<typeof vi.fn>;
  active: boolean;
  resolveRegistration(fn: UnlistenFn): void;
  rejectRegistration(err: unknown): void;
}

function createFakeListen() {
  const registrations: FakeRegistration[] = [];

  const listenFn = vi.fn(
    (eventName: string, handler: (event: { payload: unknown }) => void) => {
      let resolveRegistration!: (fn: UnlistenFn) => void;
      let rejectRegistration!: (err: unknown) => void;
      const promise = new Promise<UnlistenFn>((resolve, reject) => {
        resolveRegistration = resolve;
        rejectRegistration = reject;
      });

      const record: FakeRegistration = {
        eventName,
        handler,
        active: true,
        unlistenMock: vi.fn<() => void>(() => {
          record.active = false;
        }),
        resolveRegistration: (fn) => resolveRegistration(fn),
        rejectRegistration: (err) => rejectRegistration(err),
      };
      // vi.fn()'s inferred call signature is broader than the exact
      // `UnlistenFn` shape it satisfies at runtime; the resolve/reject
      // helpers below narrow it back with an explicit cast.
      registrations.push(record);
      return promise;
    },
  );

  /** Resolve the Nth `listen()` call with its own unlisten mock. */
  function resolveNext(index: number): void {
    const reg = registrations[index];
    if (!reg) throw new Error(`no registration at index ${index}`);
    reg.resolveRegistration(reg.unlistenMock as unknown as UnlistenFn);
  }

  function resolveAll(): void {
    registrations.forEach((_, i) => resolveNext(i));
  }

  function rejectNext(index: number, error: unknown): void {
    const reg = registrations[index];
    if (!reg) throw new Error(`no registration at index ${index}`);
    reg.rejectRegistration(error);
  }

  /** Deliver a raw (untrusted) payload as if Tauri emitted it. No-ops if this registration was already unlistened, mirroring real Tauri behavior. */
  function deliver(index: number, payload: unknown): void {
    const reg = registrations[index];
    if (!reg) throw new Error(`no registration at index ${index}`);
    if (!reg.active) return;
    reg.handler({ payload });
  }

  return {
    listenFn: listenFn as unknown as (
      eventName: string,
      handler: (event: { payload: unknown }) => void,
    ) => Promise<UnlistenFn>,
    registrations,
    resolveNext,
    resolveAll,
    rejectNext,
    deliver,
  };
}

type FakeListen = ReturnType<typeof createFakeListen>;

/** `start()`, letting every pending `listen()` call resolve immediately, then await completion. Index-stable: registrations arrive in `EVENT_DESCRIPTORS` order (state_changed=0, restart_scheduled=1, restart_exhausted=2), since `Promise.all` invokes `registerOne` for each descriptor synchronously. */
async function startFlushed(
  sub: SidecarEventSubscription,
  fake: FakeListen,
): Promise<void> {
  const pending = sub.start();
  fake.resolveAll();
  await pending;
}

const STATE_CHANGED_INDEX = 0;
const RESTART_SCHEDULED_INDEX = 1;
const RESTART_EXHAUSTED_INDEX = 2;

function newSubscription(fake: FakeListen): SidecarEventSubscription {
  return new SidecarEventSubscription({ listenFn: fake.listenFn as never });
}

// ---------------------------------------------------------------------------
// Subscription
// ---------------------------------------------------------------------------

describe("subscription", () => {
  let fake: FakeListen;
  let sub: SidecarEventSubscription;

  beforeEach(() => {
    fake = createFakeListen();
    sub = newSubscription(fake);
  });

  it("subscribes to all three canonical events", async () => {
    await startFlushed(sub, fake);

    const names = fake.registrations.map((r) => r.eventName);
    expect(names).toContain(EVENT_STATE_CHANGED);
    expect(names).toContain(EVENT_RESTART_SCHEDULED);
    expect(names).toContain(EVENT_RESTART_EXHAUSTED);
    expect(names).toHaveLength(3);
  });

  it("uses the exact event name constants, not ad hoc string literals", async () => {
    await startFlushed(sub, fake);

    expect(fake.registrations[STATE_CHANGED_INDEX]!.eventName).toBe(
      "sidecar:state_changed",
    );
    expect(fake.registrations[RESTART_SCHEDULED_INDEX]!.eventName).toBe(
      "sidecar:restart_scheduled",
    );
    expect(fake.registrations[RESTART_EXHAUSTED_INDEX]!.eventName).toBe(
      "sidecar:restart_exhausted",
    );
  });

  it("reports status started once every registration settles", async () => {
    expect(sub.getStatus()).toBe("stopped");
    await startFlushed(sub, fake);
    expect(sub.getStatus()).toBe("started");
  });
});

// ---------------------------------------------------------------------------
// Payload validation
// ---------------------------------------------------------------------------

describe("payload validation", () => {
  let fake: FakeListen;
  let sub: SidecarEventSubscription;
  let received: SidecarDomainEvent[];
  let diagnostics: SidecarDiagnostic[];

  beforeEach(async () => {
    fake = createFakeListen();
    sub = newSubscription(fake);
    received = [];
    diagnostics = [];
    sub.onEvent((e) => received.push(e));
    sub.onDiagnostic((d) => diagnostics.push(d));
    await startFlushed(sub, fake);
  });

  it("accepts a valid state_changed payload", () => {
    const payload = stateChangedPayload({ sequence: 1 });
    fake.deliver(STATE_CHANGED_INDEX, payload);

    expect(received).toEqual([{ kind: "state_changed", payload }]);
  });

  it("accepts a valid restart_scheduled payload", () => {
    const payload = restartScheduledPayload({ sequence: 1 });
    fake.deliver(RESTART_SCHEDULED_INDEX, payload);

    expect(received).toEqual([{ kind: "restart_scheduled", payload }]);
  });

  it("accepts a valid restart_exhausted payload", () => {
    const payload = restartExhaustedPayload({ sequence: 1 });
    fake.deliver(RESTART_EXHAUSTED_INDEX, payload);

    expect(received).toEqual([{ kind: "restart_exhausted", payload }]);
  });

  it("rejects a malformed payload (missing required fields)", () => {
    fake.deliver(STATE_CHANGED_INDEX, { state: "RUNNING" });

    expect(received).toHaveLength(0);
    expect(diagnostics).toEqual([
      {
        kind: "invalid_payload",
        eventName: EVENT_STATE_CHANGED,
        rawPayload: { state: "RUNNING" },
      },
    ]);
  });

  it("rejects a payload with an invalid lifecycle state", () => {
    const payload = { ...stateChangedPayload(), state: "RESTARTING" };
    fake.deliver(STATE_CHANGED_INDEX, payload);

    expect(received).toHaveLength(0);
    expect(diagnostics).toEqual([
      { kind: "invalid_payload", eventName: EVENT_STATE_CHANGED, rawPayload: payload },
    ]);
  });

  it("rejects an invalid attempt value (0 is not a valid 1-based attempt)", () => {
    const payload = restartScheduledPayload({ attempt: 0 });
    fake.deliver(RESTART_SCHEDULED_INDEX, payload);

    expect(received).toHaveLength(0);
    expect(diagnostics).toEqual([
      { kind: "invalid_payload", eventName: EVENT_RESTART_SCHEDULED, rawPayload: payload },
    ]);
  });

  it("rejects an invalid nullable field (reason neither null nor a valid StateChangeReason)", () => {
    const payload = { ...stateChangedPayload(), reason: "not-an-object" };
    fake.deliver(STATE_CHANGED_INDEX, payload);

    expect(received).toHaveLength(0);
    expect(diagnostics).toHaveLength(1);
    expect(diagnostics[0]!.kind).toBe("invalid_payload");
  });

  it("never throws out of the delivery callback for malformed input", () => {
    expect(() => fake.deliver(STATE_CHANGED_INDEX, null)).not.toThrow();
    expect(() => fake.deliver(STATE_CHANGED_INDEX, "garbage")).not.toThrow();
    expect(() => fake.deliver(STATE_CHANGED_INDEX, 42)).not.toThrow();
    expect(() => fake.deliver(STATE_CHANGED_INDEX, undefined)).not.toThrow();
    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Sequence behavior
// ---------------------------------------------------------------------------

describe("sequence filtering", () => {
  let fake: FakeListen;
  let sub: SidecarEventSubscription;
  let received: SidecarDomainEvent[];
  let diagnostics: SidecarDiagnostic[];

  beforeEach(async () => {
    fake = createFakeListen();
    sub = newSubscription(fake);
    received = [];
    diagnostics = [];
    sub.onEvent((e) => received.push(e));
    sub.onDiagnostic((d) => diagnostics.push(d));
    await startFlushed(sub, fake);
  });

  it("accepts the first valid sequence", () => {
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 1 }));

    expect(received).toHaveLength(1);
    expect(sub.getLastAppliedSequence()).toBe(1);
  });

  it("accepts a strictly newer sequence", () => {
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 1 }));
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 2 }));

    expect(received).toHaveLength(2);
    expect(sub.getLastAppliedSequence()).toBe(2);
  });

  it("rejects/ignores a duplicate sequence", () => {
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 5 }));
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 5 }));

    expect(received).toHaveLength(1);
    expect(diagnostics).toEqual([
      {
        kind: "stale_sequence",
        eventName: EVENT_STATE_CHANGED,
        sequence: 5,
        lastAppliedSequence: 5,
      },
    ]);
  });

  it("rejects/ignores an older sequence", () => {
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 10 }));
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 3 }));

    expect(received).toHaveLength(1);
    expect(sub.getLastAppliedSequence()).toBe(10);
    expect(diagnostics.at(-1)).toEqual({
      kind: "stale_sequence",
      eventName: EVENT_STATE_CHANGED,
      sequence: 3,
      lastAppliedSequence: 10,
    });
  });

  it("shares one global ordering boundary across all three event kinds", () => {
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 1 }));
    fake.deliver(RESTART_SCHEDULED_INDEX, restartScheduledPayload({ sequence: 2 }));
    // A restart_exhausted with a sequence lower than the global high-water
    // mark (2) must be dropped even though its own event kind has never
    // been seen before -- there is one counter, not three.
    fake.deliver(RESTART_EXHAUSTED_INDEX, restartExhaustedPayload({ sequence: 2 }));
    fake.deliver(RESTART_EXHAUSTED_INDEX, restartExhaustedPayload({ sequence: 3 }));

    expect(received.map((e) => e.kind)).toEqual([
      "state_changed",
      "restart_scheduled",
      "restart_exhausted",
    ]);
    expect(sub.getLastAppliedSequence()).toBe(3);
  });

  it("forwards sequence unchanged, never regenerated", () => {
    const payload = stateChangedPayload({ sequence: 42 });
    fake.deliver(STATE_CHANGED_INDEX, payload);

    const event = received[0]!;
    expect(event.kind).toBe("state_changed");
    expect((event.payload as StateChangedPayload).sequence).toBe(42);
    // Exact same object, not a copy with a substituted sequence.
    expect(event.payload).toBe(payload);
  });

  it("introduces no frontend-generated sequence field or shape change", () => {
    const payload = stateChangedPayload({ sequence: 7 });
    fake.deliver(STATE_CHANGED_INDEX, payload);

    expect(Object.keys(received[0]!.payload)).toEqual(Object.keys(payload));
  });
});

// ---------------------------------------------------------------------------
// Listener deduplication
// ---------------------------------------------------------------------------

describe("duplicate listener protection", () => {
  it("repeated start() does not create duplicate Tauri listeners", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    // Fire off three overlapping start() calls before any resolve.
    const p1 = sub.start();
    const p2 = sub.start();
    const p3 = sub.start();
    fake.resolveAll();
    await Promise.all([p1, p2, p3]);

    expect(fake.listenFn).toHaveBeenCalledTimes(3);
  });

  it("only one active listener exists per event after repeated init", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    await startFlushed(sub, fake);
    await startFlushed(sub, fake); // already started -- must be a no-op

    const names = fake.registrations.map((r) => r.eventName);
    expect(names.filter((n) => n === EVENT_STATE_CHANGED)).toHaveLength(1);
    expect(names.filter((n) => n === EVENT_RESTART_SCHEDULED)).toHaveLength(1);
    expect(names.filter((n) => n === EVENT_RESTART_EXHAUSTED)).toHaveLength(1);
  });

  it("repeated initialization is safe and does not throw", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    await expect(
      (async () => {
        await startFlushed(sub, fake);
        await sub.start();
        await sub.start();
      })(),
    ).resolves.not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Cleanup
// ---------------------------------------------------------------------------

describe("cleanup", () => {
  it("stop() invokes every unsubscribe function", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);
    await startFlushed(sub, fake);

    sub.stop();

    for (const reg of fake.registrations) {
      expect(reg.unlistenMock).toHaveBeenCalledTimes(1);
    }
  });

  it("repeated stop() is safe", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);
    await startFlushed(sub, fake);

    expect(() => {
      sub.stop();
      sub.stop();
      sub.stop();
    }).not.toThrow();

    for (const reg of fake.registrations) {
      expect(reg.unlistenMock).toHaveBeenCalledTimes(1);
    }
  });

  it("restart after stop() creates a clean listener set", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    await startFlushed(sub, fake);
    sub.stop();
    await startFlushed(sub, fake);

    expect(fake.listenFn).toHaveBeenCalledTimes(6); // 3 initial + 3 fresh
    expect(sub.getStatus()).toBe("started");
    // The first three unlisten mocks were called exactly once (from stop());
    // the second three were never unlistened (subscription still active).
    const [first3, second3] = [
      fake.registrations.slice(0, 3),
      fake.registrations.slice(3, 6),
    ];
    for (const reg of first3) expect(reg.unlistenMock).toHaveBeenCalledTimes(1);
    for (const reg of second3) expect(reg.unlistenMock).not.toHaveBeenCalled();
  });

  it("leaves no stale listeners delivering events after stop()", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);
    const received: SidecarDomainEvent[] = [];
    sub.onEvent((e) => received.push(e));

    await startFlushed(sub, fake);
    sub.stop();
    fake.deliver(STATE_CHANGED_INDEX, stateChangedPayload({ sequence: 1 }));

    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Async lifecycle races
// ---------------------------------------------------------------------------

describe("async lifecycle races", () => {
  it("start -> stop before listen() resolves leaves no active listener once it does resolve", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    const startPromise = sub.start();
    sub.stop();
    fake.resolveAll(); // late-arriving registrations
    await startPromise;

    // Every late registration must have been torn down immediately
    // rather than kept, since a stop() superseded it.
    for (const reg of fake.registrations) {
      expect(reg.unlistenMock).toHaveBeenCalledTimes(1);
    }
    expect(sub.getStatus()).toBe("stopped");
  });

  it("start -> start before listen() resolves registers exactly one listener set", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    const p1 = sub.start();
    const p2 = sub.start(); // must not kick off a second registerAll()
    fake.resolveAll();
    await Promise.all([p1, p2]);

    expect(fake.listenFn).toHaveBeenCalledTimes(3);
    expect(sub.getStatus()).toBe("started");
  });

  it("start -> stop -> start produces a clean, non-leaking listener set", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    const startPromise = sub.start();
    sub.stop();
    const restartPromise = sub.start();
    fake.resolveAll();
    await Promise.all([startPromise, restartPromise]);

    expect(sub.getStatus()).toBe("started");
    // The first generation's late registrations were unlistened; the
    // final generation's three registrations remain active.
    const activeCount = fake.registrations.filter((r) => r.active).length;
    expect(activeCount).toBe(3);
  });

  it("does not leak a listener when stop() lands between two overlapping start()s", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    sub.start();
    sub.stop();
    const finalStart = sub.start();
    fake.resolveAll();
    await finalStart;

    sub.stop();
    // Every registration across every generation must eventually be
    // unlistened exactly once -- nothing left dangling.
    for (const reg of fake.registrations) {
      expect(reg.unlistenMock).toHaveBeenCalledTimes(1);
    }
  });
});

// ---------------------------------------------------------------------------
// Subscription failures
// ---------------------------------------------------------------------------

describe("subscription failures", () => {
  it("handles a failed listener registration safely, without throwing", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);
    const diagnostics: SidecarDiagnostic[] = [];
    sub.onDiagnostic((d) => diagnostics.push(d));

    const startPromise = sub.start();
    fake.rejectNext(STATE_CHANGED_INDEX, new Error("permission denied"));
    fake.resolveNext(RESTART_SCHEDULED_INDEX);
    fake.resolveNext(RESTART_EXHAUSTED_INDEX);

    await expect(startPromise).resolves.toBeUndefined();
    expect(diagnostics).toEqual([
      {
        kind: "subscription_failed",
        eventName: EVENT_STATE_CHANGED,
        error: new Error("permission denied"),
      },
    ]);
  });

  it("does not leave the other two events unregistered when one fails", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    const startPromise = sub.start();
    fake.rejectNext(STATE_CHANGED_INDEX, new Error("boom"));
    fake.resolveNext(RESTART_SCHEDULED_INDEX);
    fake.resolveNext(RESTART_EXHAUSTED_INDEX);
    await startPromise;

    expect(sub.getStatus()).toBe("started");
    expect(fake.registrations[RESTART_SCHEDULED_INDEX]!.active).toBe(true);
    expect(fake.registrations[RESTART_EXHAUSTED_INDEX]!.active).toBe(true);
  });

  it("keeps cleanup safe after a partial registration failure", async () => {
    const fake = createFakeListen();
    const sub = newSubscription(fake);

    const startPromise = sub.start();
    fake.rejectNext(STATE_CHANGED_INDEX, new Error("boom"));
    fake.resolveNext(RESTART_SCHEDULED_INDEX);
    fake.resolveNext(RESTART_EXHAUSTED_INDEX);
    await startPromise;

    expect(() => sub.stop()).not.toThrow();
    expect(fake.registrations[RESTART_SCHEDULED_INDEX]!.unlistenMock).toHaveBeenCalledTimes(1);
    expect(fake.registrations[RESTART_EXHAUSTED_INDEX]!.unlistenMock).toHaveBeenCalledTimes(1);
  });
});
