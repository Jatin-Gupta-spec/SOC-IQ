// @vitest-environment jsdom
/**
 * Live-store and shell-integration tests for `SidecarStatusIndicator`
 * (Phase 4G-3 Part 2).
 *
 * Uses `react-dom/client` + `act`, the same live-DOM approach
 * `navigation.live.test.tsx` and Part 1's `useSidecarStatus.test.tsx`
 * already established — needed here because these tests drive real
 * state transitions through a real `SidecarProjectionStore` and
 * assert the DOM updates in response, which static rendering can't
 * observe. Each test constructs its own fresh `SidecarProjectionStore`
 * (via `SidecarStatusIndicator`'s `store` test-injection prop) rather
 * than touching the shared `sidecarProjection` singleton, matching
 * `projectionStore.test.ts`/`finalIntegration.test.ts`'s own
 * precedent of never mutating shared module state from a test.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { SidecarProjectionStore } from "../sidecar/projectionStore";
import type { SidecarStatus } from "../sidecar/types";
import { SidecarStatusIndicator } from "./SidecarStatusIndicator";
import { NavigationRegion } from "../../app/shell/NavigationRegion";

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

function statusText(): string | null {
  return container.querySelector(".sidecar-status__label")?.textContent ?? null;
}

describe("initial/unknown state (task brief §11)", () => {
  it("shows the unknown status, not a false Connected/Disconnected, before any snapshot has ever arrived", () => {
    const store = new SidecarProjectionStore();

    act(() => {
      root = createRoot(container);
      root.render(<SidecarStatusIndicator store={store} />);
    });

    expect(statusText()).toBe("Sidecar status unknown");
  });
});

describe("realistic state transitions (task brief §10)", () => {
  it("initial -> starting -> running updates the rendered status at each step", () => {
    const store = new SidecarProjectionStore();

    act(() => {
      root = createRoot(container);
      root.render(<SidecarStatusIndicator store={store} />);
    });
    expect(statusText()).toBe("Sidecar status unknown");

    act(() => {
      store.applyProjectedState(status({ state: "STARTING" }));
    });
    expect(statusText()).toBe("Sidecar starting");

    act(() => {
      store.applyProjectedState(status({ state: "RUNNING" }));
    });
    expect(statusText()).toBe("Sidecar connected");
  });

  it("running -> crashed with a pending restart -> restart exhausted reflects each transition", () => {
    const store = new SidecarProjectionStore();

    act(() => {
      root = createRoot(container);
      root.render(<SidecarStatusIndicator store={store} />);
      store.applyProjectedState(status({ state: "RUNNING" }));
    });
    expect(statusText()).toBe("Sidecar connected");

    act(() => {
      store.applyProjectedState(
        status({
          state: "CRASHED",
          restart_pending: true,
          restart_pending_attempt: 1,
          restart_attempts: 1,
        }),
      );
    });
    expect(statusText()).toBe("Sidecar restarting");

    act(() => {
      store.applyProjectedState(
        status({
          state: "CRASHED",
          restart_pending: false,
          restart_attempts: 5,
          restart_exhausted: true,
        }),
      );
    });
    expect(statusText()).toBe("Sidecar unavailable");
  });

  it("running -> stopping -> stopped reflects a clean shutdown, not a failure state", () => {
    const store = new SidecarProjectionStore();

    act(() => {
      root = createRoot(container);
      root.render(<SidecarStatusIndicator store={store} />);
      store.applyProjectedState(status({ state: "RUNNING" }));
    });

    act(() => {
      store.applyProjectedState(status({ state: "STOPPING" }));
    });
    expect(statusText()).toBe("Sidecar disconnected");

    act(() => {
      store.applyProjectedState(status({ state: "STOPPED" }));
    });
    expect(statusText()).toBe("Sidecar disconnected");
  });
});

describe("shell integration (task brief §4, §9, §10 in the checklist)", () => {
  it("NavigationRegion renders exactly one sidecar status indicator, inside the sidebar nav landmark", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <MemoryRouter>
          <NavigationRegion />
        </MemoryRouter>,
      );
    });

    const indicators = container.querySelectorAll(".sidecar-status");
    expect(indicators.length).toBe(1);

    const nav = container.querySelector("nav.app-shell__navigation-region");
    expect(nav).not.toBeNull();
    expect(nav?.querySelector(".sidecar-status")).not.toBeNull();
  });

  it("does not introduce a second nav landmark or duplicate the existing navigation items", () => {
    act(() => {
      root = createRoot(container);
      root.render(
        <MemoryRouter>
          <NavigationRegion />
        </MemoryRouter>,
      );
    });

    expect(container.querySelectorAll("nav").length).toBe(1);
  });
});
