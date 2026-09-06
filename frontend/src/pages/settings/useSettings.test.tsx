// @vitest-environment jsdom
/**
 * Live-DOM tests for `useSettings` -- mirrors
 * `pages/investigations/useInvestigationsList.test.tsx`'s established
 * `runCommand`-mocking + `act`/`createRoot` conventions (real effect
 * timing, deferred promises resolved/rejected under test control).
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

import { CommandFailedError } from "../../shared/api/client";
import { useSettings } from "./useSettings";
import type { UseSettingsResult } from "./useSettings";
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
let latestResult: UseSettingsResult;

function Probe() {
  latestResult = useSettings();
  return <div data-testid="state">{latestResult.state}</div>;
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

function render(): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe />);
  });
}

describe("initial state", () => {
  it("starts in loading state with no data", () => {
    render();

    expect(latestResult.state).toBe("loading");
    expect(latestResult.settings).toBeNull();
    expect(latestResult.error).toBeNull();
  });

  it("issues exactly one get_settings call with an empty payload", () => {
    render();

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "get_settings", {});
  });
});

describe("success", () => {
  it("resolves to success with the real settings snapshot", async () => {
    render();

    act(() => {
      nth(0).resolve(SETTINGS);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.settings).toEqual(SETTINGS);
    expect(latestResult.error).toBeNull();
  });

  it("never exposes a raw virustotal_api_key field, only the configured boolean", async () => {
    render();

    act(() => {
      nth(0).resolve(SETTINGS);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.settings).not.toHaveProperty("virustotal_api_key");
    expect(latestResult.settings?.virustotal_api_key_configured).toBe(true);
  });
});

describe("error", () => {
  it("resolves to error and preserves the real CommandFailedError", async () => {
    render();

    const failure = new CommandFailedError("get_settings", "SOME_CODE", "boom: backend failure");
    act(() => {
      nth(0).reject(failure);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("error");
    expect(latestResult.settings).toBeNull();
    expect(latestResult.error).toBe(failure);
  });
});

describe("retry", () => {
  it("starts a fresh request cycle, clearing the previous error", async () => {
    render();

    act(() => {
      nth(0).reject(new Error("network down"));
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.state).toBe("error");

    act(() => {
      latestResult.retry();
    });
    expect(latestResult.state).toBe("loading");
    expect(latestResult.error).toBeNull();

    act(() => {
      nth(1).resolve(SETTINGS);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.settings).toEqual(SETTINGS);
  });
});
