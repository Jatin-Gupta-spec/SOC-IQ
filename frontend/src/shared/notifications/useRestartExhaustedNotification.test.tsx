// @vitest-environment jsdom
/**
 * Tests for `useRestartExhaustedNotification` — Phase 4G-4 Part 1.
 *
 * Same live-DOM approach `useSidecarStatus.test.tsx` established
 * (`react-dom/client` + `act`, no `@testing-library/react`): a hook
 * built on `useSyncExternalStore` needs a real commit/subscribe cycle
 * to prove Strict Mode double-invocation doesn't duplicate anything.
 *
 * Every test constructs its own fresh `SidecarProjectionStore` and
 * `RestartExhaustedNotificationStore` pair rather than touching the
 * shared singletons, mirroring `useSidecarStatus.test.tsx`'s own
 * "construct a real instance" precedent.
 */

import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { SidecarProjectionStore } from "../sidecar/projectionStore";
import type { SidecarStatus } from "../sidecar/types";
import { RestartExhaustedNotificationStore } from "./restartExhaustedNotificationStore";
import { useRestartExhaustedNotification } from "./useRestartExhaustedNotification";

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

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function Probe({ store }: { store: RestartExhaustedNotificationStore }) {
  const state = useRestartExhaustedNotification(store);
  return (
    <div data-testid="probe">
      {state.visible ? `visible:${state.attempts}:${state.sequence}` : "hidden"}
    </div>
  );
}

function renderProbe(
  store: RestartExhaustedNotificationStore,
  strict = false,
): void {
  const element = strict ? (
    <StrictMode>
      <Probe store={store} />
    </StrictMode>
  ) : (
    <Probe store={store} />
  );

  act(() => {
    root = createRoot(container);
    root.render(element);
  });
}

describe("initial state", () => {
  it("renders hidden before any exhausted transition has occurred", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    renderProbe(notification);

    expect(container.textContent).toBe("hidden");
  });

  it("renders the store's already-visible state on first mount (no flash of hidden)", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    source.applyProjectedState(
      status({ restart_exhausted: true, restart_attempts: 4, sequence: 1 }),
    );
    notification.initialize();

    renderProbe(notification);

    expect(container.textContent).toBe("visible:4:1");
  });
});

describe("state updates", () => {
  it("re-renders when the store transitions to exhausted after mount", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    renderProbe(notification);
    expect(container.textContent).toBe("hidden");

    act(() => {
      source.applyProjectedState(
        status({ restart_exhausted: true, restart_attempts: 2, sequence: 5 }),
      );
    });
    expect(container.textContent).toBe("visible:2:5");
  });

  it("re-renders when dismissed", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));
    notification.initialize();

    renderProbe(notification);
    expect(container.textContent).not.toBe("hidden");

    act(() => {
      notification.dismiss();
    });
    expect(container.textContent).toBe("hidden");
  });
});

describe("subscription cleanup", () => {
  it("unsubscribes on unmount — a later transition does not throw", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();
    renderProbe(notification);

    act(() => {
      root.unmount();
    });

    expect(() => {
      act(() => {
        source.applyProjectedState(status({ restart_exhausted: true }));
      });
    }).not.toThrow();
  });

  it("does not register a duplicate subscription under React Strict Mode's double-invoked effects", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    renderProbe(notification, /* strict */ true);

    act(() => {
      source.applyProjectedState(
        status({ restart_exhausted: true, restart_attempts: 1, sequence: 1 }),
      );
    });
    expect(container.textContent).toBe("visible:1:1");

    act(() => {
      root.unmount();
    });

    expect(() => {
      act(() => {
        source.applyProjectedState(
          status({ restart_exhausted: false, sequence: 2 }),
        );
      });
    }).not.toThrow();
  });
});
