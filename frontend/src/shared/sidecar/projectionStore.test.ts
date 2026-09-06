/**
 * Tests for the Phase 4E-P3 Part 2D-3A projection-store foundation
 * (`projectionStore.ts`).
 *
 * Per task brief §17: "tests must test the real production store. Do
 * not mock the store itself. Do not create a second fake store
 * implementation." Every test below constructs a real
 * `SidecarProjectionStore` and drives it exclusively through its own
 * public/internal API (`subscribe`/`getState`/`dispose`/
 * `applyProjectedState`) -- `applyProjectedState` is the store's own
 * documented internal seam (see that method's doc comment), not a
 * test-only shim layered on top of it.
 */

import { describe, expect, it, vi } from "vitest";

import type { SidecarStatus } from "./types";
import {
  SidecarProjectionStore,
  type SidecarProjectionState,
} from "./projectionStore";

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

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

describe("state", () => {
  it("starts with null (no status ever applied)", () => {
    const store = new SidecarProjectionStore();
    expect(store.getState()).toBeNull();
  });

  it("getState() reflects the most recently applied state", () => {
    const store = new SidecarProjectionStore();
    const s = status({ sequence: 3, state: "CRASHED" });
    store.applyProjectedState(s);

    expect(store.getState()).toEqual(s);
  });

  it("returned state cannot be mutated by a consumer", () => {
    const store = new SidecarProjectionStore();
    store.applyProjectedState(status());

    const state = store.getState()!;
    expect(() => {
      (state as { sequence: number }).sequence = 999;
    }).toThrow();
    // The store's own view is unaffected either way.
    expect(store.getState()!.sequence).toBe(1);
  });

  it("getState() returns the same reference across calls when nothing changed", () => {
    const store = new SidecarProjectionStore();
    store.applyProjectedState(status());

    const first = store.getState();
    const second = store.getState();
    expect(first).toBe(second);
  });

  it("getState() reference changes after a real state transition", () => {
    const store = new SidecarProjectionStore();
    store.applyProjectedState(status({ sequence: 1 }));
    const first = store.getState();

    store.applyProjectedState(status({ sequence: 2 }));
    const second = store.getState();

    expect(second).not.toBe(first);
    expect(second!.sequence).toBe(2);
  });

  it("applyProjectedState is the internal mechanism state transitions go through", () => {
    const store = new SidecarProjectionStore();
    expect(store.getState()).toBeNull();

    store.applyProjectedState(status({ state: "STARTING", sequence: 1 }));
    expect(store.getState()!.state).toBe("STARTING");

    store.applyProjectedState(status({ state: "RUNNING", sequence: 2 }));
    expect(store.getState()!.state).toBe("RUNNING");
  });
});

// ---------------------------------------------------------------------------
// Subscribers
// ---------------------------------------------------------------------------

describe("subscribers", () => {
  it("notifies a single subscriber on a state change", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.subscribe(listener);

    store.applyProjectedState(status({ sequence: 1 }));

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(store.getState());
  });

  it("notifies multiple independent subscribers", () => {
    const store = new SidecarProjectionStore();
    const a = vi.fn();
    const b = vi.fn();
    const c = vi.fn();
    store.subscribe(a);
    store.subscribe(b);
    store.subscribe(c);

    store.applyProjectedState(status({ sequence: 1 }));

    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(c).toHaveBeenCalledTimes(1);
  });

  it("unsubscribe stops further notifications", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    store.applyProjectedState(status({ sequence: 1 }));
    unsubscribe();
    store.applyProjectedState(status({ sequence: 2 }));

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("repeated unsubscribe is safe", () => {
    const store = new SidecarProjectionStore();
    const unsubscribe = store.subscribe(vi.fn());

    expect(() => {
      unsubscribe();
      unsubscribe();
      unsubscribe();
    }).not.toThrow();
  });

  it("registering the same callback twice deduplicates to one active subscription", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.subscribe(listener);
    store.subscribe(listener);

    store.applyProjectedState(status({ sequence: 1 }));

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("either unsubscribe function removes a deduplicated shared subscription", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    const unsubscribeFirst = store.subscribe(listener);
    store.subscribe(listener);

    unsubscribeFirst();
    store.applyProjectedState(status({ sequence: 1 }));

    expect(listener).not.toHaveBeenCalled();
  });

  it("two distinct closures are two independent subscriptions", () => {
    const store = new SidecarProjectionStore();
    const a = vi.fn();
    const b = vi.fn();
    store.subscribe(a);
    store.subscribe(b);

    store.applyProjectedState(status({ sequence: 1 }));

    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
  });

  it("a subscriber added after an existing transition is not replayed the old state", () => {
    const store = new SidecarProjectionStore();
    store.applyProjectedState(status({ sequence: 1 }));

    const listener = vi.fn();
    store.subscribe(listener);

    expect(listener).not.toHaveBeenCalled();

    store.applyProjectedState(status({ sequence: 2 }));
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(store.getState());
  });

  it("zero subscribers: applying state does not throw", () => {
    const store = new SidecarProjectionStore();
    expect(() => store.applyProjectedState(status())).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Notification policy
// ---------------------------------------------------------------------------

describe("notification policy", () => {
  it("exactly one notification per accepted (changed) state", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.subscribe(listener);

    store.applyProjectedState(status({ sequence: 1 }));
    store.applyProjectedState(status({ sequence: 2 }));
    store.applyProjectedState(status({ sequence: 3 }));

    expect(listener).toHaveBeenCalledTimes(3);
  });

  it("no notification when the applied state is field-for-field identical", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.subscribe(listener);

    store.applyProjectedState(status({ sequence: 1 }));
    store.applyProjectedState(status({ sequence: 1 })); // identical fields, new object

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("delivers the exact new state to subscribers", () => {
    const store = new SidecarProjectionStore();
    let received: SidecarProjectionState = null;
    store.subscribe((s) => {
      received = s;
    });

    store.applyProjectedState(status({ sequence: 7, state: "FAILED" }));

    expect(received).toEqual(status({ sequence: 7, state: "FAILED" }));
  });

  it("notifies subscribers in deterministic (registration) order", () => {
    const store = new SidecarProjectionStore();
    const order: string[] = [];
    store.subscribe(() => order.push("a"));
    store.subscribe(() => order.push("b"));
    store.subscribe(() => order.push("c"));

    store.applyProjectedState(status({ sequence: 1 }));

    expect(order).toEqual(["a", "b", "c"]);
  });

  it("a single differing field is enough to trigger a notification", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.applyProjectedState(status({ restart_attempts: 1 }));
    store.subscribe(listener);

    store.applyProjectedState(status({ restart_attempts: 2 }));

    expect(listener).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

describe("lifecycle", () => {
  it("starts active", () => {
    const store = new SidecarProjectionStore();
    expect(store.getLifecycle()).toBe("active");
  });

  it("dispose() transitions to disposed", () => {
    const store = new SidecarProjectionStore();
    store.dispose();
    expect(store.getLifecycle()).toBe("disposed");
  });

  it("repeated dispose() is safe", () => {
    const store = new SidecarProjectionStore();
    expect(() => {
      store.dispose();
      store.dispose();
      store.dispose();
    }).not.toThrow();
    expect(store.getLifecycle()).toBe("disposed");
  });

  it("no notifications are delivered after dispose()", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    store.subscribe(listener);
    store.dispose();

    store.applyProjectedState(status({ sequence: 1 }));

    expect(listener).not.toHaveBeenCalled();
  });

  it("applyProjectedState() after dispose() does not change getState()", () => {
    const store = new SidecarProjectionStore();
    store.applyProjectedState(status({ sequence: 1 }));
    store.dispose();

    store.applyProjectedState(status({ sequence: 2 }));

    expect(store.getState()!.sequence).toBe(1);
  });

  it("subscriber references are released on dispose (no further delivery even via the pre-dispose closure)", () => {
    const store = new SidecarProjectionStore();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    store.dispose();

    // Calling the pre-dispose unsubscribe afterward must also be safe.
    expect(() => unsubscribe()).not.toThrow();
    store.applyProjectedState(status({ sequence: 1 }));
    expect(listener).not.toHaveBeenCalled();
  });

  it("subscribe() after dispose() returns a working no-op unsubscribe, and never fires", () => {
    const store = new SidecarProjectionStore();
    store.dispose();

    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    expect(() => unsubscribe()).not.toThrow();
    expect(listener).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Error isolation
// ---------------------------------------------------------------------------

describe("error isolation", () => {
  it("one throwing subscriber does not prevent delivery to the remaining subscribers", () => {
    const store = new SidecarProjectionStore();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const throwing = vi.fn(() => {
      throw new Error("boom");
    });
    const healthy = vi.fn();
    store.subscribe(throwing);
    store.subscribe(healthy);

    expect(() => store.applyProjectedState(status({ sequence: 1 }))).not.toThrow();

    expect(throwing).toHaveBeenCalledTimes(1);
    expect(healthy).toHaveBeenCalledTimes(1);

    consoleError.mockRestore();
  });

  it("store state remains valid and queryable after a subscriber throws", () => {
    const store = new SidecarProjectionStore();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    store.subscribe(() => {
      throw new Error("boom");
    });
    store.applyProjectedState(status({ sequence: 9, state: "TIMEOUT" }));

    expect(store.getState()).toEqual(status({ sequence: 9, state: "TIMEOUT" }));
    expect(store.getLifecycle()).toBe("active");

    consoleError.mockRestore();
  });

  it("a throwing subscriber earlier in registration order does not block a later one", () => {
    const store = new SidecarProjectionStore();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    const order: string[] = [];
    store.subscribe(() => {
      order.push("first-throws");
      throw new Error("boom");
    });
    store.subscribe(() => {
      order.push("second-runs");
    });

    store.applyProjectedState(status({ sequence: 1 }));

    expect(order).toEqual(["first-throws", "second-runs"]);

    consoleError.mockRestore();
  });
});
