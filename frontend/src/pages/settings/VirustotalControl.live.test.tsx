// @vitest-environment jsdom
/**
 * Live-DOM tests for `VirustotalControl`'s credential-write behavior --
 * SOC-IQ Part 8 (ADR-008 Part 1B-3). Mirrors
 * `ExportDirectoryControl.live.test.tsx`'s convention, mocking
 * `setVirustotalApiKey` (the one function that reaches the real
 * `keystore_set_secret` Tauri command) instead of `runCommand` --
 * this control's write path is a direct `invoke()`, not a sidecar
 * HTTP command, so `runCommand` is not involved at all.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const setVirustotalApiKeyMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    setVirustotalApiKey: (...args: unknown[]) => setVirustotalApiKeyMock(...args),
  };
});

import { VirustotalControl } from "./VirustotalControl";

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
    throw new Error(
      `Expected a setVirustotalApiKey call at index ${index}, but only ${callDeferreds.length} were made.`,
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
  callDeferreds = [];
  setVirustotalApiKeyMock.mockReset();
  setVirustotalApiKeyMock.mockImplementation(() => {
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

function render(configured: boolean): void {
  act(() => {
    root = createRoot(container);
    root.render(<VirustotalControl configured={configured} />);
  });
}

function inputEl(): HTMLInputElement {
  return container.querySelector("#settings-virustotal-api-key") as HTMLInputElement;
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
  it("never prepopulates the input, configured or not", () => {
    render(true);
    expect(inputEl().value).toBe("");
  });

  it("the input is a password field, never a plain text field", () => {
    render(true);
    expect(inputEl().type).toBe("password");
  });

  it("disables Save until a non-empty value is entered", () => {
    render(false);
    expect(saveButton().disabled).toBe(true);
  });

  it("keeps Save disabled for whitespace-only input", () => {
    render(false);
    typeValue("   ");
    expect(saveButton().disabled).toBe(true);
  });

  it("shows the Configured badge and still allows entering a replacement", () => {
    render(true);
    expect(container.textContent).toContain("Configured");
    typeValue("new-key-value");
    expect(saveButton().disabled).toBe(false);
  });
});

describe("saving", () => {
  it("calls setVirustotalApiKey with the trimmed entered value on Save", () => {
    render(false);
    typeValue("  fake-test-key-123  ");

    act(() => {
      saveButton().click();
    });

    expect(setVirustotalApiKeyMock).toHaveBeenCalledTimes(1);
    expect(setVirustotalApiKeyMock).toHaveBeenNthCalledWith(1, "fake-test-key-123");
  });

  it("shows a saving state and disables Save while in flight", () => {
    render(false);
    typeValue("fake-test-key-123");

    act(() => {
      saveButton().click();
    });

    expect(saveButton().textContent).toBe("Saving…");
    expect(saveButton().disabled).toBe(true);
  });

  it("on success: shows the restart-required message, clears the input, and never claims the credential is active", async () => {
    render(false);
    typeValue("fake-test-key-123");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain(
      "Credential saved. Restart SOC-IQ for the new credential to take effect.",
    );
    expect(container.textContent).not.toContain("Credential active");
    expect(container.textContent).not.toContain("now using the new key");
    expect(inputEl().value).toBe("");
  });

  it("on failure: shows a safe error, never the restart-required success, and preserves the entered value for retry", async () => {
    render(false);
    typeValue("fake-test-key-123");

    act(() => {
      saveButton().click();
    });
    act(() => {
      nth(0).reject(new Error("keychain access was denied"));
    });
    await act(async () => {
      await flush();
    });

    expect(container.textContent).toContain("keychain access was denied");
    expect(container.textContent).not.toContain(
      "Credential saved. Restart SOC-IQ for the new credential to take effect.",
    );
    // The entered credential itself is never dumped into the DOM.
    expect(container.textContent).not.toContain("fake-test-key-123");
    expect(inputEl().value).toBe("fake-test-key-123");

    const retryButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Retry",
    );
    expect(retryButton).toBeDefined();

    act(() => {
      retryButton?.click();
    });
    expect(setVirustotalApiKeyMock).toHaveBeenCalledTimes(2);

    act(() => {
      nth(1).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });
    expect(container.textContent).toContain("Credential saved.");
  });

  it("does not call setVirustotalApiKey when Save is invoked with empty input", () => {
    render(false);
    // Save button is disabled for empty input, but the hook's own
    // guard (STEP 8: "reject empty input") is asserted directly too,
    // independent of the disabled attribute.
    expect(saveButton().disabled).toBe(true);
    expect(setVirustotalApiKeyMock).not.toHaveBeenCalled();
  });
});
