// @vitest-environment jsdom
/**
 * Live-store and interaction tests for `RestartExhaustedNotification`
 * (Phase 4G-4 Part 1). Uses `react-dom/client` + `act`, matching
 * `SidecarStatusIndicator.live.test.tsx`'s own precedent — needed
 * here because these tests drive real transitions through a real
 * `SidecarProjectionStore` and a real click interaction, which static
 * rendering can't exercise.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SidecarProjectionStore } from "../sidecar/projectionStore";
import type { SidecarStatus } from "../sidecar/types";
import { RestartExhaustedNotificationStore } from "./restartExhaustedNotificationStore";
import { RestartExhaustedNotification } from "./RestartExhaustedNotification";

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

describe("appears on a real exhausted transition and disappears on dismiss", () => {
  it("renders nothing, then the alert, then nothing again after dismiss", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    act(() => {
      root = createRoot(container);
      root.render(<RestartExhaustedNotification store={notification} />);
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();

    act(() => {
      source.applyProjectedState(
        status({ restart_exhausted: true, restart_attempts: 3, sequence: 1 }),
      );
    });
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    expect(dismissButton).not.toBeNull();

    act(() => {
      dismissButton?.click();
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it("an onDismiss override is called instead of mutating the store directly", () => {
    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();
    source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));

    let dismissed = false;
    act(() => {
      root = createRoot(container);
      root.render(
        <RestartExhaustedNotification
          store={notification}
          onDismiss={() => {
            dismissed = true;
          }}
        />,
      );
    });

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    act(() => {
      dismissButton?.click();
    });

    expect(dismissed).toBe(true);
    // The override does not call the store's own dismiss(), so the
    // store's notification state is left exactly as the caller chose.
    expect(notification.getState().visible).toBe(true);
  });
});

describe("focus management on dismiss (MAX16-F-01)", () => {
  /**
   * Mirrors the real fallback target this component looks for
   * (`.nav-sidebar__link` in `NavigationRegion`) without depending on
   * `AppShell` itself — these tests only need a real, connected,
   * focusable element with that class to exist somewhere in the
   * document, exactly as it always does in the running app.
   */
  function appendFallbackNavLink(): HTMLAnchorElement {
    const link = document.createElement("a");
    link.href = "#";
    link.className = "nav-sidebar__link";
    link.textContent = "Dashboard";
    document.body.appendChild(link);
    return link;
  }

  it("TEST 1 — dismiss does not strand focus on <body>", () => {
    const externalButton = document.createElement("button");
    externalButton.textContent = "External control";
    document.body.appendChild(externalButton);
    externalButton.focus();
    expect(document.activeElement).toBe(externalButton);

    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    act(() => {
      root = createRoot(container);
      root.render(<RestartExhaustedNotification store={notification} />);
    });
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));
    });

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    act(() => {
      dismissButton?.focus();
      dismissButton?.click();
    });

    expect(document.activeElement).toBe(externalButton);
    externalButton.remove();
  });

  it("TEST 2 — the removed Dismiss button is never the final focus target", () => {
    const externalButton = document.createElement("button");
    document.body.appendChild(externalButton);
    externalButton.focus();

    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    act(() => {
      root = createRoot(container);
      root.render(<RestartExhaustedNotification store={notification} />);
    });
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));
    });

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    act(() => {
      dismissButton?.focus();
      dismissButton?.click();
    });

    expect(document.activeElement).not.toBe(dismissButton);
    expect(document.activeElement).not.toBe(document.body);
    expect(document.contains(document.activeElement)).toBe(true);
    externalButton.remove();
  });

  it("TEST 3 — a detached prior target is never focused; a deliberate fallback is used instead", () => {
    const fallbackLink = appendFallbackNavLink();
    const externalButton = document.createElement("button");
    document.body.appendChild(externalButton);
    externalButton.focus();

    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    act(() => {
      root = createRoot(container);
      root.render(<RestartExhaustedNotification store={notification} />);
    });
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));
    });

    // The originally-focused element is removed from the document
    // before dismissal — it must never be the target of a later
    // `.focus()` call.
    externalButton.remove();
    const focusSpy = vi.spyOn(externalButton, "focus");

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    expect(() => {
      act(() => {
        dismissButton?.click();
      });
    }).not.toThrow();

    expect(focusSpy).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(fallbackLink);
    fallbackLink.remove();
  });

  it("TEST 5 — an onDismiss override that keeps the notification visible does not move focus", () => {
    const externalButton = document.createElement("button");
    document.body.appendChild(externalButton);
    externalButton.focus();

    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();
    source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));

    let dismissed = false;
    act(() => {
      root = createRoot(container);
      root.render(
        <RestartExhaustedNotification
          store={notification}
          onDismiss={() => {
            dismissed = true;
          }}
        />,
      );
    });

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    act(() => {
      dismissButton?.focus();
      dismissButton?.click();
    });

    expect(dismissed).toBe(true);
    // The override never calls the store's dismiss(), so `visible`
    // stays true, the component stays mounted, and — per MAX16-F-01
    // §5 — focus management does nothing here; the button the person
    // is still looking at keeps focus.
    expect(notification.getState().visible).toBe(true);
    expect(document.activeElement).toBe(dismissButton);
    externalButton.remove();
  });

  it("TEST 6 — repeated dismiss/reappear cycles use the current target, never a stale one", () => {
    const firstExternal = document.createElement("button");
    firstExternal.textContent = "First";
    document.body.appendChild(firstExternal);

    const secondExternal = document.createElement("button");
    secondExternal.textContent = "Second";
    document.body.appendChild(secondExternal);

    const source = new SidecarProjectionStore();
    const notification = new RestartExhaustedNotificationStore({ source });
    notification.initialize();

    act(() => {
      root = createRoot(container);
      root.render(<RestartExhaustedNotification store={notification} />);
    });

    // Cycle 1: focus firstExternal, show, dismiss -> expect firstExternal.
    firstExternal.focus();
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: true, sequence: 1 }));
    });
    act(() => {
      container
        .querySelector<HTMLButtonElement>(".restart-exhausted-notification__dismiss")
        ?.click();
    });
    expect(document.activeElement).toBe(firstExternal);

    // A genuine new exhaustion cycle (recovered, then exhausted again).
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: false, sequence: 2 }));
    });

    // Cycle 2: focus secondExternal instead -> must not restore the
    // stale firstExternal reference from cycle 1.
    secondExternal.focus();
    act(() => {
      source.applyProjectedState(status({ restart_exhausted: true, sequence: 3 }));
    });
    act(() => {
      container
        .querySelector<HTMLButtonElement>(".restart-exhausted-notification__dismiss")
        ?.click();
    });
    expect(document.activeElement).toBe(secondExternal);
    expect(document.activeElement).not.toBe(firstExternal);

    firstExternal.remove();
    secondExternal.remove();
  });
});
