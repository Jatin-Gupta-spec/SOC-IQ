/**
 * Tests for `RestartExhaustedNotificationStore`
 * (`restartExhaustedNotification.ts`) — Phase 4G-4 Part 1.
 *
 * Follows `projectionStore.test.ts`'s own precedent: every test
 * constructs a real `RestartExhaustedNotificationStore` against an
 * isolated, real `SidecarProjectionStore` (never the shared
 * singletons), driven exclusively through public API
 * (`initialize`/`dispose`/`subscribe`/`getState`/`dismiss`) plus the
 * source store's own real `applyProjectedState()` seam.
 */

import { describe, expect, it, vi } from "vitest";

import { SidecarProjectionStore } from "../sidecar/projectionStore";
import type { SidecarStatus } from "../sidecar/types";
import { RestartExhaustedNotificationStore } from "./restartExhaustedNotificationStore";

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

function setup() {
  const source = new SidecarProjectionStore();
  const notification = new RestartExhaustedNotificationStore({ source });
  return { source, notification };
}

// ---------------------------------------------------------------------------
// 1. normal -> exhausted transition
// ---------------------------------------------------------------------------

describe("normal -> exhausted transition", () => {
  it("notifies once when restart_exhausted flips false -> true", () => {
    const { source, notification } = setup();
    notification.initialize();

    const listener = vi.fn();
    notification.subscribe(listener);

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: false }));
    expect(listener).not.toHaveBeenCalled();

    source.applyProjectedState(
      status({ sequence: 2, restart_exhausted: true, restart_attempts: 5 }),
    );

    expect(listener).toHaveBeenCalledTimes(1);
    expect(notification.getState()).toEqual({
      visible: true,
      attempts: 5,
      sequence: 2,
    });
  });

  it("carries the real attempts/sequence from the triggering snapshot, not invented values", () => {
    const { source, notification } = setup();
    notification.initialize();

    source.applyProjectedState(
      status({ sequence: 42, restart_exhausted: true, restart_attempts: 7 }),
    );

    expect(notification.getState()).toEqual({
      visible: true,
      attempts: 7,
      sequence: 42,
    });
  });
});

// ---------------------------------------------------------------------------
// 2 & 3. exhausted-without-transition / repeated identical state does not
// repeatedly notify
// ---------------------------------------------------------------------------

describe("no duplicate notification for unchanged/repeated exhausted state", () => {
  it("does not re-notify when a later snapshot changes an unrelated field but stays exhausted", () => {
    const { source, notification } = setup();
    notification.initialize();

    source.applyProjectedState(
      status({ sequence: 1, restart_exhausted: true, restart_attempts: 5 }),
    );

    const listener = vi.fn();
    notification.subscribe(listener);

    // Sequence ticks; restart_exhausted stays true -- a real, distinct
    // snapshot from the source's perspective, but not a new edge.
    source.applyProjectedState(
      status({ sequence: 2, restart_exhausted: true, restart_attempts: 5 }),
    );

    expect(listener).not.toHaveBeenCalled();
    // Still reflects the original triggering snapshot, not the later one.
    expect(notification.getState()).toEqual({
      visible: true,
      attempts: 5,
      sequence: 1,
    });
  });

  it("does not re-notify for an exactly repeated identical snapshot", () => {
    const { source, notification } = setup();
    notification.initialize();

    const exhausted = status({
      sequence: 9,
      restart_exhausted: true,
      restart_attempts: 3,
    });
    source.applyProjectedState(exhausted);

    const listener = vi.fn();
    notification.subscribe(listener);

    source.applyProjectedState(exhausted);

    expect(listener).not.toHaveBeenCalled();
  });

  it("does notify again for a genuinely new exhaustion cycle (true -> false -> true)", () => {
    const { source, notification } = setup();
    notification.initialize();

    source.applyProjectedState(
      status({ sequence: 1, restart_exhausted: true, restart_attempts: 5 }),
    );

    const listener = vi.fn();
    notification.subscribe(listener);

    // Recovered.
    source.applyProjectedState(
      status({ sequence: 2, restart_exhausted: false, restart_attempts: 0 }),
    );
    expect(listener).not.toHaveBeenCalled();

    // Exhausted again -- a real new transition.
    source.applyProjectedState(
      status({ sequence: 3, restart_exhausted: true, restart_attempts: 5 }),
    );

    expect(listener).toHaveBeenCalledTimes(1);
    expect(notification.getState()).toEqual({
      visible: true,
      attempts: 5,
      sequence: 3,
    });
  });
});

// ---------------------------------------------------------------------------
// 4. rerender does not duplicate notification
// ---------------------------------------------------------------------------

describe("rerender / repeated subscription does not duplicate notification", () => {
  it("registering the same listener reference twice only delivers one notification per transition", () => {
    const { source, notification } = setup();
    notification.initialize();

    const listener = vi.fn();
    notification.subscribe(listener);
    notification.subscribe(listener);

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("a fresh subscriber after the transition already happened does not get a replayed notification", () => {
    const { source, notification } = setup();
    notification.initialize();

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    const lateListener = vi.fn();
    notification.subscribe(lateListener);

    expect(lateListener).not.toHaveBeenCalled();
    // But the state is still readable synchronously via getState().
    expect(notification.getState().visible).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5. subscribe/unsubscribe cleanup
// ---------------------------------------------------------------------------

describe("subscription cleanup", () => {
  it("initialize() is idempotent -- a second call does not create a second source subscription", () => {
    const { source, notification } = setup();
    notification.initialize();
    notification.initialize();

    const listener = vi.fn();
    notification.subscribe(listener);

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("dispose() removes this store's subscription to source", () => {
    const { source, notification } = setup();
    notification.initialize();

    const listener = vi.fn();
    notification.subscribe(listener);
    notification.dispose();

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    expect(listener).not.toHaveBeenCalled();
    expect(notification.getLifecycle()).toBe("disposed");
  });

  it("dispose() is safe to call repeatedly and before initialize()", () => {
    const { notification } = setup();
    expect(() => {
      notification.dispose();
      notification.dispose();
    }).not.toThrow();
  });

  it("dispose() does not dispose the source store (ownership boundary)", () => {
    const { source, notification } = setup();
    notification.initialize();
    notification.dispose();

    expect(source.getLifecycle()).toBe("active");
  });

  it("an unsubscribed listener stops receiving notifications", () => {
    const { source, notification } = setup();
    notification.initialize();

    const listener = vi.fn();
    const unsubscribe = notification.subscribe(listener);
    unsubscribe();

    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    expect(listener).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 6. dismissal behavior
// ---------------------------------------------------------------------------

describe("dismissal", () => {
  it("dismiss() hides a visible notification and notifies subscribers", () => {
    const { source, notification } = setup();
    notification.initialize();
    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));

    const listener = vi.fn();
    notification.subscribe(listener);
    notification.dismiss();

    expect(notification.getState()).toEqual({ visible: false });
    expect(listener).toHaveBeenCalledWith({ visible: false });
  });

  it("dismiss() is a no-op (no notify) when nothing is visible", () => {
    const { notification } = setup();
    notification.initialize();

    const listener = vi.fn();
    notification.subscribe(listener);
    notification.dismiss();

    expect(listener).not.toHaveBeenCalled();
  });

  it("a dismissed notification does not reappear from an unrelated later snapshot while still exhausted", () => {
    const { source, notification } = setup();
    notification.initialize();
    source.applyProjectedState(status({ sequence: 1, restart_exhausted: true }));
    notification.dismiss();

    const listener = vi.fn();
    notification.subscribe(listener);

    source.applyProjectedState(status({ sequence: 2, restart_exhausted: true }));

    expect(listener).not.toHaveBeenCalled();
    expect(notification.getState()).toEqual({ visible: false });
  });
});

// ---------------------------------------------------------------------------
// 9. unknown/unexpected state safety
// ---------------------------------------------------------------------------

describe("unknown/unexpected state safety", () => {
  it("treats a null source snapshot (no status applied yet) as not-exhausted, never throws", () => {
    const { notification } = setup();
    expect(() => notification.initialize()).not.toThrow();
    expect(notification.getState()).toEqual({ visible: false });
  });

  it("seeds from an already-exhausted snapshot present at initialize() time", () => {
    const source = new SidecarProjectionStore();
    source.applyProjectedState(
      status({ sequence: 1, restart_exhausted: true, restart_attempts: 3 }),
    );
    const notification = new RestartExhaustedNotificationStore({ source });

    notification.initialize();

    expect(notification.getState()).toEqual({
      visible: true,
      attempts: 3,
      sequence: 1,
    });
  });

  it("a listener that throws does not stop delivery to remaining listeners or corrupt state", () => {
    const { source, notification } = setup();
    notification.initialize();

    const throwing = vi.fn(() => {
      throw new Error("boom");
    });
    const safe = vi.fn();
    notification.subscribe(throwing);
    notification.subscribe(safe);

    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    expect(() =>
      source.applyProjectedState(
        status({ sequence: 1, restart_exhausted: true }),
      ),
    ).not.toThrow();

    expect(safe).toHaveBeenCalledTimes(1);
    expect(notification.getState().visible).toBe(true);

    consoleError.mockRestore();
  });

  it("subscribe() after dispose() returns a safe no-op unsubscribe, never throws", () => {
    const { notification } = setup();
    notification.initialize();
    notification.dispose();

    const listener = vi.fn();
    expect(() => {
      const unsubscribe = notification.subscribe(listener);
      unsubscribe();
    }).not.toThrow();
  });
});
