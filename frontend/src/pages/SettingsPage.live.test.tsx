// @vitest-environment jsdom
/**
 * `SettingsPage` live-DOM integration tests -- SOC-IQ MAX-18 Phase
 * 2A-1 (MAX18-F-01, dirty-state foundation).
 *
 * `SettingsPage.test.tsx` (static-markup, no effects) already covers
 * this page's loading/error/success rendering; the per-field dirty
 * mechanics themselves are already covered in isolation by
 * `settings/useSettingsFieldSave.test.tsx` and
 * `settings/useVirustotalKeySave.test.tsx`.
 *
 * This file's job is narrower and specific to MAX18-F-01: proving,
 * with all three real controls mounted together the way the actual
 * page renders them, that each control's dirty state (observable
 * here via its own Save button's `disabled` attribute -- the
 * existing, already-tested signal each control derives its dirty
 * flag from) is genuinely independent -- multiple can be dirty at
 * once, and saving one never clears another's.
 *
 * `useSettings` is mocked the same way `SettingsPage.test.tsx` mocks
 * it (a fixed successful result, no loading state to await); the two
 * underlying transports the three controls actually call --
 * `runCommand` for Theme/Export Directory and `setVirustotalApiKey`
 * for the VirusTotal key -- are mocked the same way their own
 * `*.live.test.tsx` files mock them.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useSettingsMock = vi.fn();
const runCommandMock = vi.fn();
const setVirustotalApiKeyMock = vi.fn();

vi.mock("./settings/useSettings", () => ({
  useSettings: (...args: unknown[]) => useSettingsMock(...args),
}));

vi.mock("../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../shared/api/client")>(
    "../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
    setVirustotalApiKey: (...args: unknown[]) => setVirustotalApiKeyMock(...args),
  };
});

import { SettingsPage } from "./SettingsPage";
import type { GetSettingsResult } from "../shared/api/types";

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

function nthRunCommand(index: number): DeferredCall {
  const deferred = runCommandDeferreds[index];
  if (!deferred) {
    throw new Error(
      `Expected a runCommand call at index ${index}, but only ${runCommandDeferreds.length} were made.`,
    );
  }
  return deferred;
}

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
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
  setVirustotalApiKeyMock.mockImplementation(() => new Promise(() => {}));
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(<SettingsPage />);
  });
}

function themeSelect(): HTMLSelectElement {
  return container.querySelector("#settings-theme-select") as HTMLSelectElement;
}

function exportDirectoryInput(): HTMLInputElement {
  return container.querySelector("#settings-export-directory") as HTMLInputElement;
}

function virustotalInput(): HTMLInputElement {
  return container.querySelector("#settings-virustotal-api-key") as HTMLInputElement;
}

function saveButtons(): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll(".settings-page__save-button"));
}

function themeSaveButton(): HTMLButtonElement {
  const button = saveButtons()[0];
  if (!button) {
    throw new Error("Expected a Theme Save button.");
  }
  return button;
}

function exportDirectorySaveButton(): HTMLButtonElement {
  const button = saveButtons()[1];
  if (!button) {
    throw new Error("Expected an Export Directory Save button.");
  }
  return button;
}

function virustotalSaveButton(): HTMLButtonElement {
  const button = saveButtons()[2];
  if (!button) {
    throw new Error("Expected a VirusTotal Save button.");
  }
  return button;
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

describe("initial state", () => {
  it("starts every control clean -- all three Save buttons disabled", () => {
    render();

    expect(saveButtons()).toHaveLength(3);
    expect(themeSaveButton().disabled).toBe(true);
    expect(exportDirectorySaveButton().disabled).toBe(true);
    expect(virustotalSaveButton().disabled).toBe(true);
  });
});

describe("independent dirty tracking", () => {
  it("editing one control leaves the other two clean", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");

    expect(themeSaveButton().disabled).toBe(false);
    expect(exportDirectorySaveButton().disabled).toBe(true);
    expect(virustotalSaveButton().disabled).toBe(true);
  });

  it("all three controls can be dirty at the same time", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");

    expect(themeSaveButton().disabled).toBe(false);
    expect(exportDirectorySaveButton().disabled).toBe(false);
    expect(virustotalSaveButton().disabled).toBe(false);
  });

  it("saving one control does not clear another dirty control's state", async () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");

    act(() => {
      themeSaveButton().click();
    });
    act(() => {
      nthRunCommand(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });

    // The saved control is clean again; the untouched-but-edited one
    // is still dirty -- saving Theme must not have reset it.
    expect(themeSaveButton().disabled).toBe(true);
    expect(exportDirectorySaveButton().disabled).toBe(false);
  });

  it("a failed save on one control does not clear or otherwise affect another dirty control", async () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");

    act(() => {
      exportDirectorySaveButton().click();
    });
    act(() => {
      nthRunCommand(0).reject(new Error("disk write failed"));
    });
    await act(async () => {
      await flush();
    });

    // The failed save leaves Export Directory dirty; Theme was never
    // touched by that save and must remain dirty too.
    expect(exportDirectorySaveButton().disabled).toBe(false);
    expect(themeSaveButton().disabled).toBe(false);
  });

  it("editing a control back to its persisted value returns only that control to clean", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setSelectValue(themeSelect(), "Dark Mode (SOC-IQ Standard)");

    expect(themeSaveButton().disabled).toBe(true);
    expect(exportDirectorySaveButton().disabled).toBe(false);
  });
});

describe("secret handling", () => {
  it("never renders the entered VirusTotal key as visible text anywhere on the page", () => {
    // The typed value legitimately lives in the password input's own
    // DOM `value` (exactly how any real controlled input works, and
    // how `VirustotalControl.live.test.tsx` already asserts it's
    // readable back from `inputEl().value` for editing/retry) -- the
    // dirty-state addition here must not cause it to additionally
    // leak into any rendered text node: a note, a status message, or
    // another control's markup.
    render();

    setInputValue(virustotalInput(), "super-secret-key-value");

    expect(virustotalInput().value).toBe("super-secret-key-value");
    expect(container.textContent).not.toContain("super-secret-key-value");
  });
});

describe("unmount", () => {
  it("unmounting with in-flight saves on multiple controls does not throw", async () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");

    act(() => {
      themeSaveButton().click();
      exportDirectorySaveButton().click();
      virustotalSaveButton().click();
    });

    expect(() => {
      act(() => {
        root.unmount();
      });
    }).not.toThrow();

    // Recreate a live root so the shared `afterEach`'s own
    // `root.unmount()` has something to act on.
    act(() => {
      root = createRoot(container);
    });

    // Resolving after unmount must not throw or warn via a stale
    // `setState` on an unmounted tree.
    expect(() => {
      act(() => {
        nthRunCommand(0).resolve({ field: "theme", updated: true });
        nthRunCommand(1).resolve({ field: "export_directory", updated: true });
      });
    }).not.toThrow();

    await act(async () => {
      await flush();
    });
  });
});
