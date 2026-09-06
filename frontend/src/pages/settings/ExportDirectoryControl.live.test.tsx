// @vitest-environment jsdom
/**
 * Live-DOM tests for `ExportDirectoryControl` -- same convention as
 * `settings/ThemeControl.live.test.tsx`.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
  };
});

import { ExportDirectoryControl } from "./ExportDirectoryControl";

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

let callDeferreds: DeferredCall[];

function nth(index: number): DeferredCall {
  const deferred = callDeferreds[index];
  if (!deferred) {
    throw new Error(`Expected a runCommand call at index ${index}, but only ${callDeferreds.length} were made.`);
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
  callDeferreds = [];
  runCommandMock.mockReset();
  runCommandMock.mockImplementation(() => {
    const deferred = makeDeferred();
    callDeferreds.push(deferred);
    return deferred.promise;
  });
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(persistedExportDirectory: string): void {
  act(() => {
    root = createRoot(container);
    root.render(<ExportDirectoryControl persistedExportDirectory={persistedExportDirectory} />);
  });
}

function inputEl(): HTMLInputElement {
  return container.querySelector("#settings-export-directory") as HTMLInputElement;
}

function saveButton(): HTMLButtonElement {
  return container.querySelector(".settings-page__save-button") as HTMLButtonElement;
}

function typeValue(value: string): void {
  const input = inputEl();
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  )?.set;
  act(() => {
    nativeSetter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("rendering", () => {
  it("loads the persisted export directory into the field", () => {
    render("/home/analyst/output");
    expect(inputEl().value).toBe("/home/analyst/output");
  });

  it("disables Save until the value is edited", () => {
    render("/home/analyst/output");
    expect(saveButton().disabled).toBe(true);
  });
});

describe("editing", () => {
  it("tracks dirty state once the value differs from the persisted baseline", () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");
    expect(saveButton().disabled).toBe(false);
  });

  it("is not dirty again once edited back to the persisted baseline", () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");
    typeValue("/home/analyst/output");
    expect(saveButton().disabled).toBe(true);
  });
});

describe("saving", () => {
  it("calls save_settings with only the export_directory field on Save", () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");

    act(() => {
      saveButton().click();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "save_settings", {
      export_directory: "/home/analyst/new-output",
    });
  });

  it("shows a saving state and disables Save while in flight", () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");

    act(() => {
      saveButton().click();
    });

    expect(saveButton().textContent).toBe("Saving…");
    expect(saveButton().disabled).toBe(true);
  });

  it("shows a success message and clears dirty state after a successful save", async () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("Export directory saved.");
    expect(saveButton().disabled).toBe(true);
  });

  it("shows the real error message and a working Retry action after a failed save", async () => {
    render("/home/analyst/output");
    typeValue("/home/analyst/new-output");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).reject(new Error("permission denied"));
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("permission denied");
    // A failed save leaves the field dirty -- nothing was persisted.
    expect(saveButton().disabled).toBe(false);

    const retryButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Retry",
    );
    expect(retryButton).toBeDefined();

    act(() => {
      retryButton?.click();
    });
    expect(runCommandMock).toHaveBeenCalledTimes(2);

    act(() => {
      nth(1).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(container.textContent).toContain("Export directory saved.");
  });
});
