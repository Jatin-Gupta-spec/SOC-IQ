// @vitest-environment jsdom
/**
 * Live-DOM tests for `useSettingsFieldSave` -- same `runCommand`
 * mocking + `act`/`createRoot` convention as
 * `pages/settings/useSettings.test.tsx` and
 * `pages/investigations/useInvestigationsList.test.tsx`.
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

import { useSettingsFieldSave } from "./useSettingsFieldSave";
import type { UseSettingsFieldSaveResult } from "./useSettingsFieldSave";

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
let latestResult: UseSettingsFieldSaveResult;

function Probe({ field, persistedValue }: { field: "theme" | "export_directory"; persistedValue: string }) {
  latestResult = useSettingsFieldSave(field, persistedValue);
  return <div data-testid="value">{latestResult.value}</div>;
}

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

function render(field: "theme" | "export_directory", persistedValue: string): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe field={field} persistedValue={persistedValue} />);
  });
}

describe("initial state", () => {
  it("starts with the persisted value, not dirty, idle", () => {
    render("export_directory", "/home/analyst/output");

    expect(latestResult.value).toBe("/home/analyst/output");
    expect(latestResult.dirty).toBe(false);
    expect(latestResult.saveStatus).toEqual({ status: "idle" });
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("dirty tracking", () => {
  it("becomes dirty when the value is edited away from the persisted baseline", () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });

    expect(latestResult.dirty).toBe(true);
  });

  it("is not dirty again once the value is edited back to the persisted baseline", () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.setValue("/home/analyst/output");
    });

    expect(latestResult.dirty).toBe(false);
  });
});

describe("save", () => {
  it("calls save_settings with exactly the edited field", () => {
    render("theme", "Dark Mode (SOC-IQ Standard)");

    act(() => {
      latestResult.setValue("High Contrast Dark");
    });
    act(() => {
      latestResult.save();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "save_settings", { theme: "High Contrast Dark" });
  });

  it("enters saving state immediately", () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.save();
    });

    expect(latestResult.saveStatus).toEqual({ status: "saving" });
  });

  it("resolves to success and clears dirty state on a successful save", async () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);
  });

  it("resolves to error, preserving the real error message, on a failed save", async () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).reject(new Error("disk write failed"));
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.saveStatus).toEqual({ status: "error", message: "disk write failed" });
    // A failed save leaves the edit dirty -- nothing was actually persisted.
    expect(latestResult.dirty).toBe(true);
  });

  it("retries by calling save again after a failure", async () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).reject(new Error("disk write failed"));
    });
    await act(async () => {
      await flush();
    });

    act(() => {
      latestResult.save();
    });
    expect(runCommandMock).toHaveBeenCalledTimes(2);
    expect(latestResult.saveStatus).toEqual({ status: "saving" });

    act(() => {
      nth(1).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.saveStatus).toEqual({ status: "success" });
  });

  it("a stale success from an older save cannot overwrite a newer save's success baseline", async () => {
    render("theme", "Dark Mode (SOC-IQ Standard)");

    // Save A: "High Contrast Dark"
    act(() => {
      latestResult.setValue("High Contrast Dark");
    });
    act(() => {
      latestResult.save();
    });

    // Before A resolves, edit again and issue Save B: "Light Mode"
    act(() => {
      latestResult.setValue("Light Mode");
    });
    act(() => {
      latestResult.save();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(2);

    // B (the newer request, index 1) resolves first.
    act(() => {
      nth(1).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);

    // A (the older, stale request, index 0) resolves late.
    act(() => {
      nth(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });

    // The stale success must not resurrect "High Contrast Dark" as the
    // baseline, and must not falsely mark the already-saved "Light Mode"
    // value as dirty.
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);
    expect(latestResult.value).toBe("Light Mode");
  });

  it("a stale failure from an older save cannot overwrite a newer save's success", async () => {
    render("export_directory", "/home/analyst/output");

    // Save A
    act(() => {
      latestResult.setValue("/home/analyst/output-a");
    });
    act(() => {
      latestResult.save();
    });

    // Before A resolves, edit again and issue Save B
    act(() => {
      latestResult.setValue("/home/analyst/output-b");
    });
    act(() => {
      latestResult.save();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(2);

    // B (the newer request) succeeds first.
    act(() => {
      nth(1).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.saveStatus).toEqual({ status: "success" });

    // A (the older, stale request) fails late.
    act(() => {
      nth(0).reject(new Error("disk write failed"));
    });
    await act(async () => {
      await flush();
    });

    // The stale failure must not overwrite B's already-applied success.
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);
  });

  it("clears a prior success/error status as soon as the value is edited again", async () => {
    render("export_directory", "/home/analyst/output");

    act(() => {
      latestResult.setValue("/home/analyst/new-output");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).resolve({ field: "export_directory", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.saveStatus).toEqual({ status: "success" });

    act(() => {
      latestResult.setValue("/home/analyst/yet-another-output");
    });

    expect(latestResult.saveStatus).toEqual({ status: "idle" });
  });
});
