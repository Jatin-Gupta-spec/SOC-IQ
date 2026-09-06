// @vitest-environment jsdom
/**
 * Settings navigation guard -- full-app live tests. SOC-IQ MAX-18
 * Phase 2A-3 (MAX18-F-01).
 *
 * Renders the real `<App />` (real `HashRouter`, real `AppShell` --
 * sidebar, command palette, and `SettingsNavigationGuardDialog` all
 * wired exactly as production composes them) starting on the real
 * Settings route, following `navigation.live.test.tsx`'s own
 * `window.location.hash` convention for choosing the initial
 * `HashRouter` location. `useSettings` and the API client are mocked
 * exactly the way `SettingsPage.dirtyAggregate.live.test.tsx` already
 * does, so the three real controls (Theme, Export Directory,
 * VirusTotal) drive real dirty state without a backend.
 *
 * Covers every numbered behavior in this checkpoint's task brief:
 *  1. clean Settings -> navigation succeeds
 *  2. dirty Settings -> navigation blocked pending decision
 *  3. Stay -> URL/route remains Settings
 *  4. Leave -> destination reached
 *  5. repeated navigation attempts
 *  6. rapid navigation attempts
 *  7. multiple dirty fields
 *  8. save clears protection
 *  9. failed save preserves protection
 * 10. CommandPalette navigation
 * 11. sidebar navigation
 * 12. history behavior where supported
 *
 * ...plus a short regression pass for MAX-15 (command palette focus
 * restore), MAX-16 (restart-exhausted notification, unaffected by
 * this checkpoint but co-mounted in the same `AppShell`), and MAX-17
 * (route-change focus management).
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * SOC-IQ GATE 2 STEP 5 — forensic finding (see the fuller note in
 * `router.live.test.tsx`). On a clean-Windows CI run, Test 4's first
 * navigation to Analyze in this file (`"navigates to the
 * originally-attempted destination"`) failed with the destination
 * `<main>` absent after `waitForRouteToSettle()` -- Analyze's lazy
 * chunk had not been touched by any earlier test in this file, so it
 * paid the same first-import cold-transform cost documented in
 * `router.live.test.tsx`, exceeding the polling budget below. This
 * project's own reference environment passes every test in this file
 * with zero flakiness (verified as part of this investigation), and
 * no other test/describe block here reported a failure. Widening this
 * file's own polling budget and Vitest timeout, scoped here only,
 * gives a colder/slower environment real headroom without weakening
 * what's asserted (dialog/hash/destination-`<main>` checks are
 * unchanged).
 */
vi.setConfig({ testTimeout: 9_000 });

const useSettingsMock = vi.fn();
const runCommandMock = vi.fn();
const setVirustotalApiKeyMock = vi.fn();

vi.mock("../../pages/settings/useSettings", () => ({
  useSettings: (...args: unknown[]) => useSettingsMock(...args),
}));

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
    setVirustotalApiKey: (...args: unknown[]) => setVirustotalApiKeyMock(...args),
  };
});

const { App } = await import("../App");
const { settingsNavigationGuard } = await import(
  "../../pages/settings/settingsNavigationGuardStore"
);
const { restartExhaustedNotification } = await import(
  "../../shared/notifications/restartExhaustedNotificationStore"
);

import type { GetSettingsResult } from "../../shared/api/types";

const SETTINGS: GetSettingsResult = {
  theme: "Dark Mode (SOC-IQ Standard)",
  export_directory: "/home/analyst/output",
  virustotal_api_key_configured: true,
};

interface DeferredCall {
  readonly promise: Promise<unknown>;
  resolve: (value: unknown) => void;
  reject: (error: unknown) => void;
}

function makeDeferred(): DeferredCall {
  let resolve!: (value: unknown) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<unknown>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

let runCommandDeferreds: DeferredCall[];

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  window.location.hash = "#/settings";
  container = document.createElement("div");
  document.body.appendChild(container);

  useSettingsMock.mockReset();
  useSettingsMock.mockReturnValue({
    state: "success",
    settings: SETTINGS,
    error: null,
    retry: vi.fn(),
  });

  runCommandDeferreds = [];
  runCommandMock.mockReset();
  runCommandMock.mockImplementation(() => {
    const deferred = makeDeferred();
    runCommandDeferreds.push(deferred);
    return deferred.promise;
  });

  setVirustotalApiKeyMock.mockReset();
  setVirustotalApiKeyMock.mockImplementation(() => Promise.resolve());
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
  window.location.hash = "";
  // Defensive: a test that leaves a confirmation pending (it
  // shouldn't, but nothing else would reset it) must not leak into
  // the next test's initial state.
  settingsNavigationGuard.cancel();
  restartExhaustedNotification.dispose();
});

/**
 * Waits for a route transition to fully settle, mirroring
 * `router.live.test.tsx`'s own polling helper -- a fixed number of
 * short real-time ticks rather than a single `act(async)` await.
 *
 * This must tick unconditionally (not merely "while `Loading ` text
 * is present"): React Router v7's default transition behavior for a
 * declarative `<Routes>` update that suspends (a not-yet-loaded lazy
 * page chunk) keeps the *previous* route's already-committed content
 * on screen while the new one resolves in the background, rather
 * than swapping to the `<Suspense>` fallback immediately -- so a
 * "Loading " substring never appears at all for this case, and a
 * check that only polls while it's present would return instantly,
 * before the destination page has actually committed. Always ticking
 * a handful of real timers first (regardless of current content) and
 * only then falling through to the same "Loading " watch handles both
 * this deferred-transition case and a genuinely slow/fallback-visible
 * load.
 */
async function waitForRouteToSettle(): Promise<void> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
  }
  // 120 attempts (6s) rather than the original 40 (2s) -- see the
  // GATE 2 STEP 5 forensic note above `vi.setConfig` at the top of
  // this file. The 50ms interval and the condition checked are both
  // unchanged.
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (!container.textContent?.includes("Loading ")) {
      return;
    }
    // eslint-disable-next-line no-await-in-loop
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
  }
}

async function render(): Promise<void> {
  await act(async () => {
    root = createRoot(container);
    root.render(<App />);
  });
  await waitForRouteToSettle();
}

function themeSelect(): HTMLSelectElement {
  return container.querySelector("#settings-theme-select") as HTMLSelectElement;
}

function exportDirectoryInput(): HTMLInputElement {
  return container.querySelector("#settings-export-directory") as HTMLInputElement;
}

function saveButtons(): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll(".settings-page__save-button"));
}

function themeSaveButton(): HTMLButtonElement {
  return saveButtons()[0] as HTMLButtonElement;
}

function setSelectValue(select: HTMLSelectElement, value: string): void {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    "value",
  )?.set;
  act(() => {
    nativeSetter?.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  )?.set;
  act(() => {
    nativeSetter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

/** Makes the Theme control dirty by picking the other supported value. */
function makeThemeDirty(): void {
  setSelectValue(themeSelect(), "High Contrast Dark");
}

function sidebarLink(ariaLabel: string): HTMLAnchorElement {
  const link = Array.from(container.querySelectorAll("a")).find(
    (anchor) => anchor.getAttribute("aria-label") === ariaLabel,
  );
  if (!link) {
    throw new Error(`No nav link found with aria-label "${ariaLabel}"`);
  }
  return link as HTMLAnchorElement;
}

function clickSidebar(ariaLabel: string): void {
  act(() => {
    sidebarLink(ariaLabel).dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
    );
  });
}

function dialog(): HTMLElement | null {
  return container.querySelector('[role="alertdialog"]');
}

function stayButton(): HTMLButtonElement | null {
  return container.querySelector(".settings-nav-guard__button--stay");
}

function leaveButton(): HTMLButtonElement | null {
  return container.querySelector(".settings-nav-guard__button--leave");
}

function openCommandPalette(): void {
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }),
    );
  });
}

function paletteOption(label: string): HTMLLIElement {
  const option = Array.from(
    container.querySelectorAll('[role="option"]'),
  ).find((node) => node.textContent?.includes(label));
  if (!option) {
    throw new Error(`No command palette option found for "${label}"`);
  }
  return option as HTMLLIElement;
}

describe("1. clean Settings -> navigation succeeds", () => {
  it("navigates immediately with no confirmation when Settings is clean", async () => {
    await render();
    expect(dialog()).toBeNull();

    clickSidebar("Dashboard");

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/dashboard");
  });
});

describe("2. dirty Settings -> navigation blocked pending decision", () => {
  it("blocks the sidebar click and opens the confirmation instead of navigating", async () => {
    await render();
    makeThemeDirty();

    clickSidebar("Dashboard");

    expect(window.location.hash).toBe("#/settings");
    expect(dialog()).not.toBeNull();
    expect(dialog()?.textContent).toContain("Unsaved changes");
  });
});

describe("3. Stay -> URL/route remains Settings", () => {
  it("dismisses the confirmation and leaves the route and edits untouched", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");
    expect(dialog()).not.toBeNull();

    act(() => {
      stayButton()?.click();
    });

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/settings");
    // The in-progress edit is still there -- Stay never discards it.
    expect(themeSelect().value).toBe("High Contrast Dark");
  });
});

describe("4. Leave -> destination reached", () => {
  it("navigates to the originally-attempted destination", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Analyze");
    expect(dialog()).not.toBeNull();

    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/analyze");
    expect(container.querySelector('[aria-label="Analyze page"]')).not.toBeNull();
  });

  it("discards the local edit -- a later visit to Settings is not falsely dirty", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");
    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    clickSidebar("Settings");
    await waitForRouteToSettle();

    console.log("DEBUG after settings click hash=", window.location.hash);
    console.log("DEBUG themeSelect exists?", !!themeSelect());
    console.log("DEBUG container select count", container.querySelectorAll("select").length);

    expect(dialog()).toBeNull();
    expect(themeSelect().value).toBe("Dark Mode (SOC-IQ Standard)");

    // And a real, unrelated navigation away from this fresh, clean
    // mount is never blocked by the previous visit's discarded edit.
    clickSidebar("Reports");
    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/reports");
  });
});

describe("5. repeated navigation attempts", () => {
  it("re-targets a single open confirmation to the latest attempted destination", async () => {
    await render();
    makeThemeDirty();

    clickSidebar("Dashboard");
    expect(dialog()).not.toBeNull();
    clickSidebar("Analyze");

    expect(container.querySelectorAll('[role="alertdialog"]')).toHaveLength(1);
    act(() => {
      leaveButton()?.click();
    });
    expect(window.location.hash).toBe("#/analyze");
  });
});

describe("6. rapid navigation attempts", () => {
  it("multiple synchronous clicks on the same link never open more than one dialog", async () => {
    await render();
    makeThemeDirty();

    act(() => {
      for (let i = 0; i < 5; i += 1) {
        sidebarLink("Dashboard").dispatchEvent(
          new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
        );
      }
    });

    expect(container.querySelectorAll('[role="alertdialog"]')).toHaveLength(1);
    expect(window.location.hash).toBe("#/settings");
  });
});

describe("7. multiple dirty fields", () => {
  it("guards navigation when more than one control is dirty, and Leave discards both", async () => {
    await render();
    makeThemeDirty();
    setInputValue(exportDirectoryInput(), "/tmp/new-output");

    clickSidebar("Dashboard");
    expect(dialog()).not.toBeNull();

    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    expect(window.location.hash).toBe("#/dashboard");

    clickSidebar("Settings");
    await waitForRouteToSettle();
    expect(themeSelect().value).toBe("Dark Mode (SOC-IQ Standard)");
    expect(exportDirectoryInput().value).toBe("/home/analyst/output");
  });
});

describe("8. save clears protection", () => {
  it("a successful save clears the guard, and navigation succeeds without confirmation", async () => {
    await render();
    makeThemeDirty();

    act(() => {
      themeSaveButton().click();
    });
    expect(runCommandDeferreds).toHaveLength(1);

    await act(async () => {
      runCommandDeferreds[0]!.resolve({ theme: "High Contrast Dark" });
      await flush();
    });

    clickSidebar("Dashboard");

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/dashboard");
  });
});

describe("9. failed save preserves protection", () => {
  it("a rejected save leaves the guard active -- navigation is still blocked", async () => {
    await render();
    makeThemeDirty();

    act(() => {
      themeSaveButton().click();
    });
    expect(runCommandDeferreds).toHaveLength(1);

    await act(async () => {
      runCommandDeferreds[0]!.reject(new Error("backend unavailable"));
      await flush();
    });

    clickSidebar("Dashboard");

    expect(dialog()).not.toBeNull();
    expect(window.location.hash).toBe("#/settings");
  });
});

describe("10. CommandPalette navigation", () => {
  it("blocks a palette-selected destination while dirty and confirms before navigating", async () => {
    await render();
    makeThemeDirty();

    openCommandPalette();
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();

    act(() => {
      paletteOption("Dashboard").dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
      );
    });

    // The palette itself closes; the confirmation takes its place.
    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(dialog()).not.toBeNull();
    expect(window.location.hash).toBe("#/settings");

    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    expect(window.location.hash).toBe("#/dashboard");
  });

  it("navigates immediately via the palette when Settings is clean", async () => {
    await render();

    openCommandPalette();
    act(() => {
      paletteOption("Analyze").dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }),
      );
    });

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/analyze");
  });
});

describe("11. sidebar navigation", () => {
  it("intercepts a direct sidebar click identically to the general case", async () => {
    await render();
    makeThemeDirty();

    clickSidebar("Reports");

    expect(dialog()).not.toBeNull();
    expect(window.location.hash).toBe("#/settings");
  });

  it("clicking the already-active Settings link while dirty is never intercepted", async () => {
    await render();
    makeThemeDirty();

    clickSidebar("Settings");

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/settings");
  });
});

describe("12. history behavior where supported", () => {
  it("Stay commits no history entry -- the hash never changes", async () => {
    await render();
    makeThemeDirty();
    const before = window.location.hash;

    clickSidebar("Dashboard");
    act(() => {
      stayButton()?.click();
    });

    expect(window.location.hash).toBe(before);
  });

  it("Leave commits exactly the confirmed destination to history", async () => {
    await render();
    makeThemeDirty();

    clickSidebar("Reports");
    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    expect(window.location.hash).toBe("#/reports");
  });
});

describe("regression: MAX-15 (command palette focus restore)", () => {
  it("still restores focus to the trigger after closing the palette on a clean Settings page", async () => {
    await render();
    const trigger = sidebarLink("Dashboard");
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    openCommandPalette();
    act(() => {
      container
        .querySelector<HTMLButtonElement>(".command-palette-backdrop__dismiss")
        ?.click();
    });

    expect(document.activeElement).toBe(trigger);
  });
});

describe("regression: MAX-16 (restart-exhausted notification)", () => {
  it("still mounts and remains independent of the navigation guard dialog", async () => {
    await render();
    act(() => {
      restartExhaustedNotification.initialize();
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(dialog()).toBeNull();

    makeThemeDirty();
    clickSidebar("Dashboard");

    // The guard's alertdialog and the (still hidden) restart notice
    // coexist without either interfering with the other's mount.
    expect(dialog()).not.toBeNull();
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});

describe("regression: MAX-17 (route-change focus management)", () => {
  it("still focuses the destination page's main landmark after a guard-confirmed Leave", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");

    act(() => {
      leaveButton()?.click();
    });
    await waitForRouteToSettle();

    const main = container.querySelector("main.page-layout");
    expect(main).not.toBeNull();
    expect(document.activeElement).toBe(main);
  });
});

describe("13. Escape -> Stay (Phase 2A-4)", () => {
  it("dismisses the confirmation, keeps the route on Settings, and preserves the edit -- the same result as clicking Stay", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");
    expect(dialog()).not.toBeNull();

    act(() => {
      dialog()?.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
    });

    expect(dialog()).toBeNull();
    expect(window.location.hash).toBe("#/settings");
    expect(themeSelect().value).toBe("High Contrast Dark");
  });

  it("still lets a subsequent navigation attempt open a fresh confirmation -- Escape does not leave the guard stuck", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");
    act(() => {
      dialog()?.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Escape",
          bubbles: true,
          cancelable: true,
        }),
      );
    });
    expect(dialog()).toBeNull();

    clickSidebar("Reports");

    expect(dialog()).not.toBeNull();
  });
});

describe("14. keyboard focus containment (Phase 2A-4)", () => {
  it("Tab from Leave does not escape into the sidebar behind the backdrop", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");
    expect(dialog()).not.toBeNull();

    act(() => {
      leaveButton()?.focus();
    });
    expect(document.activeElement).toBe(leaveButton());

    act(() => {
      leaveButton()?.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Tab",
          bubbles: true,
          cancelable: true,
        }),
      );
    });

    expect(document.activeElement).toBe(stayButton());
  });

  it("focus never falls to document.body while the confirmation is pending", async () => {
    await render();
    makeThemeDirty();
    clickSidebar("Dashboard");

    expect(document.activeElement).not.toBe(document.body);
  });
});
