// @vitest-environment jsdom
/**
 * `SettingsPage` dirty-state aggregation tests -- SOC-IQ MAX-18 Phase
 * 2A-2 (MAX18-F-01).
 *
 * `SettingsPage.live.test.tsx` (Phase 2A-1) already proves each real
 * control's own `dirty` signal is independent when all three are
 * mounted together. This file is scoped to what Phase 2A-2 adds on
 * top of that: the page-level `settingsDirty` aggregate, observable
 * here via the non-visual `data-settings-dirty` marker `SettingsPage`
 * renders around its success view (see that component's own doc
 * comment). Same mocking approach as `SettingsPage.live.test.tsx`.
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

function nthSetVirustotalApiKey(index: number): DeferredCall {
  const deferred = virustotalDeferreds[index];
  if (!deferred) {
    throw new Error(
      `Expected a setVirustotalApiKey call at index ${index}, but only ${virustotalDeferreds.length} were made.`,
    );
  }
  return deferred;
}

let virustotalDeferreds: DeferredCall[];

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

  virustotalDeferreds = [];
  setVirustotalApiKeyMock.mockReset();
  setVirustotalApiKeyMock.mockImplementation(() => {
    const deferred = makeDeferred();
    virustotalDeferreds.push(deferred);
    return deferred.promise;
  });
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

/** The non-visual aggregate marker `SettingsPage` renders -- see its
 * own doc comment (MAX-18 Phase 2A-2). */
function settingsDirtyAttribute(): string | null {
  return container.querySelector("[data-settings-dirty]")?.getAttribute("data-settings-dirty") ?? null;
}

describe("aggregate initial state", () => {
  it("is clean when every control is clean", () => {
    render();

    expect(settingsDirtyAttribute()).toBe("false");
  });
});

describe("required combination matrix", () => {
  it("clean / clean / clean -> clean", () => {
    render();

    expect(settingsDirtyAttribute()).toBe("false");
  });

  it("dirty / clean / clean -> dirty", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("clean / dirty / clean -> dirty", () => {
    render();

    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("clean / clean / dirty -> dirty", () => {
    render();

    setInputValue(virustotalInput(), "fake-test-key-123");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("dirty / dirty / clean -> dirty", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("dirty / clean / dirty -> dirty", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(virustotalInput(), "fake-test-key-123");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("clean / dirty / dirty -> dirty", () => {
    render();

    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");

    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("dirty / dirty / dirty -> dirty", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");

    expect(settingsDirtyAttribute()).toBe("true");
  });
});

describe("saving clears only the saved control's contribution", () => {
  it("saving Theme while Export Directory and VirusTotal stay dirty leaves the aggregate dirty", async () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");

    act(() => {
      themeSaveButton().click();
    });
    act(() => {
      nthRunCommand(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(themeSaveButton().disabled).toBe(true);
    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("saving every dirty control in turn returns the aggregate to clean", async () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    setInputValue(virustotalInput(), "fake-test-key-123");
    expect(settingsDirtyAttribute()).toBe("true");

    act(() => {
      themeSaveButton().click();
    });
    act(() => {
      nthRunCommand(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(settingsDirtyAttribute()).toBe("true");

    act(() => {
      exportDirectorySaveButton().click();
    });
    act(() => {
      nthRunCommand(1).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(settingsDirtyAttribute()).toBe("true");

    act(() => {
      virustotalSaveButton().click();
    });
    act(() => {
      nthSetVirustotalApiKey(0).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });
    expect(settingsDirtyAttribute()).toBe("false");
  });

  it("a failed save preserves that control's dirty contribution to the aggregate", async () => {
    render();

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

    expect(exportDirectorySaveButton().disabled).toBe(false);
    expect(settingsDirtyAttribute()).toBe("true");
  });

  it("a failed VirusTotal save preserves the aggregate as dirty", async () => {
    render();

    setInputValue(virustotalInput(), "fake-test-key-123");

    act(() => {
      virustotalSaveButton().click();
    });
    act(() => {
      nthSetVirustotalApiKey(0).reject(new Error("keychain access was denied"));
    });
    await act(async () => {
      await flush();
    });

    expect(virustotalSaveButton().disabled).toBe(false);
    expect(settingsDirtyAttribute()).toBe("true");
  });
});

describe("unmount / remount", () => {
  it("a fresh mount never falsely reports dirty after a prior instance was left dirty", () => {
    render();

    setSelectValue(themeSelect(), "High Contrast Dark");
    setInputValue(exportDirectoryInput(), "/home/analyst/new-output");
    expect(settingsDirtyAttribute()).toBe("true");

    act(() => {
      root.unmount();
    });
    render();

    expect(settingsDirtyAttribute()).toBe("false");
  });

  it("unmounting with in-flight saves on multiple controls does not throw and does not falsely mark a later remount dirty", async () => {
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

    expect(() => {
      act(() => {
        nthRunCommand(0).resolve({ field: "theme", updated: true });
        nthRunCommand(1).resolve({ field: "export_directory", updated: true });
        nthSetVirustotalApiKey(0).resolve(undefined);
      });
    }).not.toThrow();

    await act(async () => {
      await flush();
    });

    render();
    expect(settingsDirtyAttribute()).toBe("false");
  });
});

describe("secret handling", () => {
  it("the VirusTotal edit buffer never leaks into the dirty aggregate's own markup", () => {
    render();

    setInputValue(virustotalInput(), "super-secret-key-value");

    expect(virustotalInput().value).toBe("super-secret-key-value");
    expect(container.textContent).not.toContain("super-secret-key-value");
    // The aggregate marker itself carries only the boolean, never the
    // buffer's contents (see `settingsDirty.ts`'s own doc comment:
    // the combinator takes booleans only).
    expect(settingsDirtyAttribute()).toBe("true");
  });
});
