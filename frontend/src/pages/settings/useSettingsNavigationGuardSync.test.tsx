// @vitest-environment jsdom
/**
 * `useSettingsNavigationGuardSync` tests -- SOC-IQ MAX-18 Phase 2A-3
 * (MAX18-F-01). Same `Probe`/`createRoot`/`act` convention as
 * `useSettingsPageDirty.test.tsx`. Exercises the hook against an
 * isolated `SettingsNavigationGuardStore` instance (never the shared
 * singleton), so nothing here can leak into another test file.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useSettingsNavigationGuardSync } from "./useSettingsNavigationGuardSync";
import { SettingsNavigationGuardStore } from "./settingsNavigationGuardStore";

let container: HTMLDivElement;
let root: Root;
let store: SettingsNavigationGuardStore;

function Probe({ dirty }: { readonly dirty: boolean }) {
  useSettingsNavigationGuardSync(dirty, store);
  return <div>{String(dirty)}</div>;
}

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  store = new SettingsNavigationGuardStore();
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(dirty: boolean): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe dirty={dirty} />);
  });
}

function rerender(dirty: boolean): void {
  act(() => {
    root.render(<Probe dirty={dirty} />);
  });
}

describe("forwarding", () => {
  it("forwards the initial dirty value to the store", () => {
    render(true);
    expect(store.isDirty()).toBe(true);
  });

  it("forwards false as the initial value", () => {
    render(false);
    expect(store.isDirty()).toBe(false);
  });

  it("forwards every subsequent change", () => {
    render(false);
    expect(store.isDirty()).toBe(false);

    rerender(true);
    expect(store.isDirty()).toBe(true);

    rerender(false);
    expect(store.isDirty()).toBe(false);
  });
});

describe("unmount clears stale dirty state", () => {
  it("clears the store's dirty flag on unmount, even while dirty", () => {
    render(true);
    expect(store.isDirty()).toBe(true);

    act(() => {
      root.unmount();
    });

    expect(store.isDirty()).toBe(false);
  });

  it("clears the store's dirty flag on unmount even when already clean", () => {
    render(false);

    act(() => {
      root.unmount();
    });

    expect(store.isDirty()).toBe(false);
  });

  it("does not clear on every settingsDirty change -- only on real unmount", () => {
    render(true);
    rerender(true);
    rerender(true);

    // Still dirty across re-renders with an unchanged value -- the
    // unmount-only cleanup effect never fired.
    expect(store.isDirty()).toBe(true);
  });
});

describe("fresh mount after unmount", () => {
  it("a later mount starts the store clean again after a prior unmount cleared it", () => {
    render(true);
    act(() => {
      root.unmount();
    });
    expect(store.isDirty()).toBe(false);

    render(false);
    expect(store.isDirty()).toBe(false);
  });
});
