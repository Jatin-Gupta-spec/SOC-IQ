// @vitest-environment jsdom
/**
 * Live-DOM tests for `ThemeControl` -- same `runCommand`-mocking +
 * `act`/`createRoot` convention as `settings/useSettings.test.tsx`.
 * Exercises the real `<select>` element and real `save_settings`
 * call, not a mocked `useSettingsFieldSave`, so this also covers that
 * hook's wiring into a real control end to end.
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

import { ThemeControl } from "./ThemeControl";

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

function render(persistedTheme: string): void {
  act(() => {
    root = createRoot(container);
    root.render(<ThemeControl persistedTheme={persistedTheme} />);
  });
}

function selectEl(): HTMLSelectElement {
  return container.querySelector("#settings-theme-select") as HTMLSelectElement;
}

function saveButton(): HTMLButtonElement {
  return container.querySelector(".settings-page__save-button") as HTMLButtonElement;
}

function setSelectValue(value: string): void {
  const select = selectEl();
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    "value",
  )?.set;
  act(() => {
    nativeSetter?.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("MAX12-F-01: not-yet-applied disclosure", () => {
  it("always shows the disclosure that the selection is saved but not applied, regardless of which supported theme is persisted", () => {
    render("Dark Mode (SOC-IQ Standard)");
    expect(container.textContent).toContain("saved but not yet applied to the interface");

    root.unmount();
    container.remove();
    container = document.createElement("div");
    document.body.appendChild(container);
    render("High Contrast Dark");
    expect(container.textContent).toContain("saved but not yet applied to the interface");
  });

  it("still shows the disclosure for an unsupported/legacy persisted value, alongside the unsupported-value note", () => {
    render("Legacy Blue Theme");
    expect(container.textContent).toContain("saved but not yet applied to the interface");
    expect(container.textContent).toContain("not one of the supported options");
  });

  it("keeps showing the disclosure after changing the selection but before saving", () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");
    expect(container.textContent).toContain("saved but not yet applied to the interface");
  });

  it("keeps showing the disclosure after a successful save, alongside the success message", async () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("Theme saved.");
    expect(container.textContent).toContain("saved but not yet applied to the interface");
  });

  it("renders the disclosure as a plain note, not an alert or a success/error status", () => {
    render("Dark Mode (SOC-IQ Standard)");
    const notes = Array.from(container.querySelectorAll('[role="note"]'));
    const disclosure = notes.find((el) => el.textContent?.includes("saved but not yet applied to the interface"));
    expect(disclosure).toBeDefined();
  });
});

describe("rendering a supported persisted theme", () => {
  it("renders the two supported options, with the persisted value selected", () => {
    render("Dark Mode (SOC-IQ Standard)");

    const options = Array.from(selectEl().options).map((option) => option.value);
    expect(options).toEqual(["Dark Mode (SOC-IQ Standard)", "High Contrast Dark"]);
    expect(selectEl().value).toBe("Dark Mode (SOC-IQ Standard)");
  });

  it("disables Save until a change is made", () => {
    render("Dark Mode (SOC-IQ Standard)");
    expect(saveButton().disabled).toBe(true);
  });
});

describe("rendering an unsupported persisted theme", () => {
  it("does not silently coerce or overwrite it -- shows a placeholder and a note", () => {
    render("Legacy Blue Theme");

    expect(selectEl().value).toBe("");
    expect(container.textContent).toContain("Legacy Blue Theme");
    expect(container.textContent).toContain("not one of the supported options");
    expect(runCommandMock).not.toHaveBeenCalled();
  });
});

describe("changing the theme", () => {
  it("tracks dirty state once a different value is selected", () => {
    render("Dark Mode (SOC-IQ Standard)");

    setSelectValue("High Contrast Dark");

    expect(saveButton().disabled).toBe(false);
  });

  it("is not dirty again if the original value is re-selected", () => {
    render("Dark Mode (SOC-IQ Standard)");

    setSelectValue("High Contrast Dark");
    setSelectValue("Dark Mode (SOC-IQ Standard)");

    expect(saveButton().disabled).toBe(true);
  });
});

describe("saving", () => {
  it("calls save_settings with only the theme field on Save", () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");

    act(() => {
      saveButton().click();
    });

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "save_settings", { theme: "High Contrast Dark" });
  });

  it("shows a saving state and disables Save while in flight", () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");

    act(() => {
      saveButton().click();
    });

    expect(saveButton().textContent).toBe("Saving…");
    expect(saveButton().disabled).toBe(true);
  });

  it("shows a success message after a successful save", async () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("Theme saved.");
    expect(saveButton().disabled).toBe(true);
  });

  it("shows the real error message and a Retry action after a failed save", async () => {
    render("Dark Mode (SOC-IQ Standard)");
    setSelectValue("High Contrast Dark");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).reject(new Error("settings file is read-only"));
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("settings file is read-only");
    const retryButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Retry",
    );
    expect(retryButton).toBeDefined();

    act(() => {
      retryButton?.click();
    });
    expect(runCommandMock).toHaveBeenCalledTimes(2);

    act(() => {
      nth(1).resolve({ field: "theme", updated: true });
    });
    await act(async () => {
      await flush();
    });
    expect(container.textContent).toContain("Theme saved.");
  });
});
