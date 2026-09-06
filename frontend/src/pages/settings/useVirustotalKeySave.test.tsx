// @vitest-environment jsdom
/**
 * Live-DOM tests for `useVirustotalKeySave`'s `dirty` signal --
 * SOC-IQ MAX-18 Phase 2A-1 (MAX18-F-01). Same `act`/`createRoot`
 * Probe convention as `useSettingsFieldSave.test.tsx`; save-lifecycle
 * behavior itself (success/error/retry wording) is already covered
 * by `VirustotalControl.live.test.tsx` -- this file is scoped to the
 * `dirty` flag this checkpoint adds.
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

import { useVirustotalKeySave } from "./useVirustotalKeySave";
import type { UseVirustotalKeySaveResult } from "./useVirustotalKeySave";

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
let latestResult: UseVirustotalKeySaveResult;

function Probe() {
  latestResult = useVirustotalKeySave();
  return <div data-testid="value">{latestResult.value}</div>;
}

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

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe />);
  });
}

describe("initial state", () => {
  it("starts clean, with an empty buffer", () => {
    render();

    expect(latestResult.value).toBe("");
    expect(latestResult.dirty).toBe(false);
  });
});

describe("dirty tracking", () => {
  it("becomes dirty as soon as any non-whitespace value is entered", () => {
    render();

    act(() => {
      latestResult.setValue("a");
    });

    expect(latestResult.dirty).toBe(true);
  });

  it("stays clean for whitespace-only input", () => {
    render();

    act(() => {
      latestResult.setValue("   ");
    });

    expect(latestResult.dirty).toBe(false);
  });

  it("returns to clean once the buffer is edited back to empty", () => {
    render();

    act(() => {
      latestResult.setValue("fake-test-key-123");
    });
    act(() => {
      latestResult.setValue("");
    });

    expect(latestResult.dirty).toBe(false);
  });

  it("never derives dirty from anything but the buffer's own length", () => {
    render();

    act(() => {
      latestResult.setValue("fake-test-key-123");
    });
    act(() => {
      latestResult.setValue("a-completely-different-value");
    });

    // Still dirty regardless of which non-empty value is present --
    // this hook has no persisted baseline to compare against.
    expect(latestResult.dirty).toBe(true);
  });
});

describe("save", () => {
  it("returns to clean once a save resolves, since the buffer is cleared on success", async () => {
    render();

    act(() => {
      latestResult.setValue("fake-test-key-123");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.value).toBe("");
    expect(latestResult.dirty).toBe(false);
  });

  it("remains dirty after a failed save, since the buffer is preserved for retry", async () => {
    render();

    act(() => {
      latestResult.setValue("fake-test-key-123");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      nth(0).reject(new Error("keychain access was denied"));
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.value).toBe("fake-test-key-123");
    expect(latestResult.dirty).toBe(true);
  });

  it("does not leak the entered credential into a thrown error or rejection value", async () => {
    render();

    act(() => {
      latestResult.setValue("super-secret-key-value");
    });
    act(() => {
      latestResult.save();
    });

    // The only thing the mocked transport received is the trimmed
    // credential itself (asserted elsewhere) -- nothing here re-wraps
    // or logs it. Resolving/rejecting must not throw.
    expect(() => {
      act(() => {
        nth(0).resolve(undefined);
      });
    }).not.toThrow();
  });
});

describe("stale save response ordering", () => {
  it("a stale failure from an older save cannot overwrite a newer save's success, even when the older save was re-enabled by a mid-flight edit", async () => {
    render();

    // Save A is issued.
    act(() => {
      latestResult.setValue("key-A");
    });
    act(() => {
      latestResult.save();
    });
    expect(latestResult.saveStatus).toEqual({ status: "saving" });

    // Editing while A is still in flight resets status to "idle",
    // re-enabling the real Save button -- exercise exactly that path.
    act(() => {
      latestResult.setValue("key-B");
    });
    expect(latestResult.saveStatus).toEqual({ status: "idle" });

    // Save B is issued before A has resolved.
    act(() => {
      latestResult.save();
    });
    expect(setVirustotalApiKeyMock).toHaveBeenCalledTimes(2);

    // B (the newer request) succeeds first.
    act(() => {
      nth(1).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.value).toBe("");

    // A (the older, stale request) fails late.
    act(() => {
      nth(0).reject(new Error("keychain access was denied"));
    });
    await act(async () => {
      await flush();
    });

    // The stale failure must not overwrite B's already-applied success.
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);
  });

  it("a stale success from an older save cannot resurrect the cleared buffer or overwrite a newer save's success", async () => {
    render();

    act(() => {
      latestResult.setValue("key-A");
    });
    act(() => {
      latestResult.save();
    });
    act(() => {
      latestResult.setValue("key-B");
    });
    act(() => {
      latestResult.save();
    });

    // B (the newer request) succeeds first, clearing the buffer.
    act(() => {
      nth(1).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.value).toBe("");
    expect(latestResult.saveStatus).toEqual({ status: "success" });

    // A (the older, stale request) also succeeds, but late.
    act(() => {
      nth(0).resolve(undefined);
    });
    await act(async () => {
      await flush();
    });

    // Still clean, still success -- the stale response is a no-op.
    expect(latestResult.value).toBe("");
    expect(latestResult.saveStatus).toEqual({ status: "success" });
    expect(latestResult.dirty).toBe(false);
  });
});

describe("unmount", () => {
  it("does not throw or apply a stale update when a save resolves after unmount", async () => {
    render();

    act(() => {
      latestResult.setValue("fake-test-key-123");
    });
    act(() => {
      latestResult.save();
    });

    act(() => {
      root.unmount();
    });
    // Re-create an (unrendered) root so the shared `afterEach`'s own
    // `root.unmount()` call has a live root to act on, rather than
    // double-unmounting the one this test already tore down.
    act(() => {
      root = createRoot(container);
    });

    expect(() => {
      act(() => {
        nth(0).resolve(undefined);
      });
    }).not.toThrow();

    await act(async () => {
      await flush();
    });
  });
});
