/**
 * `SettingsNavigationGuardStore` tests -- SOC-IQ MAX-18 Phase 2A-3
 * (MAX18-F-01). Pure store logic, no DOM/React needed -- a fresh
 * instance per test (this class's own documented reasoning), never
 * the shared `settingsNavigationGuard` singleton, so nothing here can
 * leak into another test or into the live/integration suites.
 */

import { describe, expect, it, vi } from "vitest";
import {
  SettingsNavigationGuardStore,
  SETTINGS_NAVIGATION_PATH,
} from "./settingsNavigationGuardStore";

const ELSEWHERE = "/dashboard";

describe("initial state", () => {
  it("starts clean: not dirty, nothing pending", () => {
    const store = new SettingsNavigationGuardStore();
    expect(store.isDirty()).toBe(false);
    expect(store.getState()).toEqual({ pending: false });
  });
});

describe("clean Settings -> navigation succeeds", () => {
  it("allows navigation away and opens no confirmation when not dirty", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(false);

    expect(store.requestNavigation(ELSEWHERE)).toBe("allowed");
    expect(store.getState()).toEqual({ pending: false });
  });

  it("does not intercept navigation to Settings itself, dirty or not", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);

    expect(store.requestNavigation(SETTINGS_NAVIGATION_PATH)).toBe("allowed");
    expect(store.getState()).toEqual({ pending: false });
  });
});

describe("dirty Settings -> navigation blocked pending decision", () => {
  it("blocks navigation to a different destination and opens a pending confirmation", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);

    expect(store.requestNavigation(ELSEWHERE)).toBe("blocked");
    expect(store.getState()).toEqual({ pending: true, targetPath: ELSEWHERE });
  });

  it("notifies subscribers exactly once when a confirmation opens", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    const listener = vi.fn();
    store.subscribe(listener);

    store.requestNavigation(ELSEWHERE);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith({ pending: true, targetPath: ELSEWHERE });
  });
});

describe("Stay", () => {
  it("clears the pending confirmation without touching dirty state", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    store.requestNavigation(ELSEWHERE);

    store.cancel();

    expect(store.getState()).toEqual({ pending: false });
    expect(store.isDirty()).toBe(true);
  });

  it("is a no-op (no notify) when nothing is pending", () => {
    const store = new SettingsNavigationGuardStore();
    const listener = vi.fn();
    store.subscribe(listener);

    store.cancel();

    expect(listener).not.toHaveBeenCalled();
    expect(store.getState()).toEqual({ pending: false });
  });
});

describe("Leave", () => {
  it("returns the pending destination, clears pending, and clears dirty", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    store.requestNavigation(ELSEWHERE);

    const target = store.confirmLeave();

    expect(target).toBe(ELSEWHERE);
    expect(store.getState()).toEqual({ pending: false });
    expect(store.isDirty()).toBe(false);
  });

  it("returns null and does not notify when nothing is pending", () => {
    const store = new SettingsNavigationGuardStore();
    const listener = vi.fn();
    store.subscribe(listener);

    expect(store.confirmLeave()).toBeNull();
    expect(listener).not.toHaveBeenCalled();
  });

  it("does not loop: the destination the guard reports is immediately allowed on the next request", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    store.requestNavigation(ELSEWHERE);
    const target = store.confirmLeave();

    // Simulates the caller re-deriving a navigation attempt to the
    // same destination it was just handed -- must never re-block.
    expect(store.requestNavigation(target as string)).toBe("allowed");
  });
});

describe("repeated and rapid navigation attempts", () => {
  it("re-targets a single pending confirmation rather than stacking a second one", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    const listener = vi.fn();

    store.requestNavigation("/analyze");
    store.subscribe(listener);
    store.requestNavigation("/reports");
    store.requestNavigation("/reports");

    expect(store.getState()).toEqual({ pending: true, targetPath: "/reports" });
    // One notification per call, but always the same single pending
    // object shape -- never two confirmations coexisting.
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("identical rapid-fire requests for the same destination stay a single pending confirmation", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);

    for (let i = 0; i < 5; i += 1) {
      expect(store.requestNavigation(ELSEWHERE)).toBe("blocked");
    }

    expect(store.getState()).toEqual({ pending: true, targetPath: ELSEWHERE });
  });
});

describe("subscriber isolation", () => {
  it("one throwing listener does not prevent delivery to the rest or corrupt state", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    const throwing = vi.fn(() => {
      throw new Error("boom");
    });
    const healthy = vi.fn();
    store.subscribe(throwing);
    store.subscribe(healthy);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => store.requestNavigation(ELSEWHERE)).not.toThrow();

    expect(healthy).toHaveBeenCalledTimes(1);
    expect(store.getState()).toEqual({ pending: true, targetPath: ELSEWHERE });
    consoleError.mockRestore();
  });

  it("unsubscribing stops future notifications", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    unsubscribe();
    store.requestNavigation(ELSEWHERE);

    expect(listener).not.toHaveBeenCalled();
  });
});

describe("stale dirty state", () => {
  it("a later setDirty(false) makes a previously-blocked destination immediately allowed", () => {
    const store = new SettingsNavigationGuardStore();
    store.setDirty(true);
    expect(store.requestNavigation(ELSEWHERE)).toBe("blocked");
    store.cancel();

    // Simulates SettingsPage unmounting (useSettingsNavigationGuardSync's
    // cleanup) after Stay -- e.g. some other unrelated unmount path.
    store.setDirty(false);

    expect(store.requestNavigation(ELSEWHERE)).toBe("allowed");
  });

  it("a fresh instance never inherits another instance's dirty state", () => {
    const first = new SettingsNavigationGuardStore();
    first.setDirty(true);

    const second = new SettingsNavigationGuardStore();

    expect(second.isDirty()).toBe(false);
    expect(second.requestNavigation(ELSEWHERE)).toBe("allowed");
  });
});
