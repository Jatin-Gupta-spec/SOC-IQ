// @vitest-environment jsdom
/**
 * AppShell integration tests for the restart-exhausted notification
 * mount — Phase 4G-4 Part 2 (task brief §14 items 1-3, 5, 6, 8-10).
 *
 * `AppShell.tsx` mounts `RestartExhaustedNotification` with no store
 * prop, i.e. against the one real application-wide
 * `restartExhaustedNotification` singleton (itself reading the real
 * `sidecarProjection` singleton) — the same composition-root wiring
 * production code uses. These tests therefore exercise that real
 * default wiring end to end (mirroring
 * `RestartExhaustedNotification.live.test.tsx`'s use of
 * `act`/`createRoot`, but through `AppShell` instead of the bare
 * component), rather than injecting an isolated store the way the
 * Part 1 component-level tests do. Each test calls `initialize()` /
 * `dispose()` on the two real singletons itself (mirroring what
 * `App.tsx`'s effects do at runtime) and always disposes in
 * `afterEach`, so no state leaks from one test into the next.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { AppShell } from "./AppShell";
import { restartExhaustedNotification } from "../../shared/notifications/restartExhaustedNotificationStore";
import { sidecarProjection } from "../../shared/sidecar/projectionStore";
import type { SidecarStatus } from "../../shared/sidecar/types";

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
  // Real singletons: always dispose, mirroring App.tsx's own cleanup,
  // so a later test never inherits this test's subscription or
  // edge-detection memory.
  restartExhaustedNotification.dispose();
});

function renderApp(initialPath = "/dashboard"): void {
  act(() => {
    root = createRoot(container);
    root.render(
      <MemoryRouter initialEntries={[initialPath]}>
        <AppShell>
          <div>page content</div>
        </AppShell>
      </MemoryRouter>,
    );
  });
}

describe("AppShell restart-exhausted notification integration", () => {
  it("shows nothing, then the alert, on a real exhausted transition", () => {
    renderApp();
    act(() => {
      restartExhaustedNotification.initialize();
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();

    act(() => {
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, restart_attempts: 3, sequence: 1 }),
      );
    });

    const alert = container.querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert?.textContent).toContain("Sidecar restart attempts exhausted");
  });

  it("does not obscure or remove the navigation region while showing the alert", () => {
    renderApp();
    act(() => {
      restartExhaustedNotification.initialize();
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, sequence: 1 }),
      );
    });

    expect(
      container.querySelector(".app-shell__navigation-region"),
    ).not.toBeNull();
    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);
  });

  it("does not duplicate the alert on rerender with unchanged state", () => {
    renderApp();
    act(() => {
      restartExhaustedNotification.initialize();
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, sequence: 1 }),
      );
    });
    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);

    // A rerender of the whole tree with no state change.
    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AppShell>
            <div>page content, rerendered</div>
          </AppShell>
        </MemoryRouter>,
      );
    });
    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);

    // A repeated, identical exhausted snapshot (e.g. `sequence`
    // unchanged) must not fire a second notification.
    act(() => {
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, sequence: 1 }),
      );
    });
    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);
  });

  it("remains visible, and does not duplicate, across a route change", () => {
    renderApp("/dashboard");
    act(() => {
      restartExhaustedNotification.initialize();
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, sequence: 1 }),
      );
    });
    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);

    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/analyze"]}>
          <AppShell>
            <div>analyze page content</div>
          </AppShell>
        </MemoryRouter>,
      );
    });

    expect(container.querySelectorAll('[role="alert"]').length).toBe(1);
    expect(container.textContent).toContain("analyze page content");
  });

  it("dismissing hides the alert without mutating sidecar lifecycle state", () => {
    renderApp();
    act(() => {
      restartExhaustedNotification.initialize();
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, restart_attempts: 3, sequence: 1 }),
      );
    });

    const dismissButton = container.querySelector<HTMLButtonElement>(
      ".restart-exhausted-notification__dismiss",
    );
    expect(dismissButton).not.toBeNull();

    act(() => {
      dismissButton?.click();
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
    // The underlying sidecar projection snapshot is untouched by
    // dismissal — dismissing the notification is not a restart, and
    // must not resurface a "recovered" appearance on its own.
    expect(sidecarProjection.getState()?.restart_exhausted).toBe(true);
  });

  it("does not resurrect a dismissed notification on an unrelated rerender", () => {
    renderApp();
    act(() => {
      restartExhaustedNotification.initialize();
      sidecarProjection.applyProjectedState(
        status({ restart_exhausted: true, sequence: 1 }),
      );
    });
    act(() => {
      container
        .querySelector<HTMLButtonElement>(
          ".restart-exhausted-notification__dismiss",
        )
        ?.click();
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();

    act(() => {
      root.render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AppShell>
            <div>page content, rerendered</div>
          </AppShell>
        </MemoryRouter>,
      );
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});
