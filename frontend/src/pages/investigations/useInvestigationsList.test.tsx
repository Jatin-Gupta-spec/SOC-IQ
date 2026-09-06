// @vitest-environment jsdom
/**
 * Live-DOM tests for `useInvestigationsList` -- mirrors
 * `pages/investigation/useInvestigation.test.tsx`'s established
 * `runCommand`-mocking + `act`/`createRoot` conventions (real effect
 * timing, real Strict Mode double-invocation) rather than introducing
 * `@testing-library/react` as a second test approach.
 */

import { act, StrictMode } from "react";
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

import { CommandFailedError, CommandNetworkError } from "../../shared/api/client";
import { useInvestigationsList } from "./useInvestigationsList";
import type { UseInvestigationsListResult } from "./useInvestigationsList";
import type { InvestigationSummary } from "../../shared/api/types";

const INVESTIGATION: InvestigationSummary = {
  investigation_id: 7,
  report_name: "report.txt",
  risk_score: 42,
  severity: "high",
  confidence: 0.9,
  status: "COMPLETED",
  analyzed_at: "2026-08-26T00:00:00",
};

const INVESTIGATION_2: InvestigationSummary = {
  investigation_id: 9,
  report_name: "second-report.txt",
  risk_score: 12,
  severity: "low",
  confidence: 0.5,
  status: "COMPLETED",
  analyzed_at: "2026-08-26T01:00:00",
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
let latestResult: UseInvestigationsListResult;

function Probe({ strict = false }: { strict?: boolean }) {
  return strict ? (
    <StrictMode>
      <ProbeInner />
    </StrictMode>
  ) : (
    <ProbeInner />
  );
}

function ProbeInner() {
  latestResult = useInvestigationsList();
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

function render(strict = false): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe strict={strict} />);
  });
}

describe("initial state", () => {
  it("starts in loading state with no data", () => {
    render();

    expect(latestResult.state).toBe("loading");
    expect(latestResult.investigations).toBeNull();
    expect(latestResult.error).toBeNull();
  });

  it("issues exactly one list_investigations call with an empty payload", () => {
    render();

    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "list_investigations", {});
  });
});

describe("success", () => {
  it("resolves to success with the real investigation list", async () => {
    render();

    act(() => {
      nth(0).resolve([INVESTIGATION, INVESTIGATION_2]);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.investigations).toEqual([INVESTIGATION, INVESTIGATION_2]);
    expect(latestResult.error).toBeNull();
  });

  it("resolves to success with a genuinely empty list, distinct from not-yet-loaded", async () => {
    render();

    act(() => {
      nth(0).resolve([]);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.investigations).toEqual([]);
    expect(Array.isArray(latestResult.investigations)).toBe(true);
  });
});

describe("error", () => {
  it("resolves to error and preserves the real CommandFailedError", async () => {
    render();

    const failure = new CommandFailedError("list_investigations", "SOME_CODE", "boom: backend failure");
    act(() => {
      nth(0).reject(failure);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("error");
    expect(latestResult.investigations).toBeNull();
    expect(latestResult.error).toBe(failure);
  });

  it("resolves to error for a network failure (sidecar unreachable)", async () => {
    render();

    const failure = new CommandNetworkError("list_investigations", new Error("offline"));
    act(() => {
      nth(0).reject(failure);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("error");
    expect(latestResult.error).toBe(failure);
  });
});

describe("retry", () => {
  it("starts a fresh request cycle, clearing previous data/error", async () => {
    render();

    const failure = new CommandFailedError("list_investigations", "SOME_CODE", "boom");
    act(() => {
      nth(0).reject(failure);
    });
    await act(async () => {
      await flush();
    });
    expect(latestResult.state).toBe("error");

    act(() => {
      latestResult.retry();
    });

    expect(latestResult.state).toBe("loading");
    expect(latestResult.investigations).toBeNull();
    expect(latestResult.error).toBeNull();
    expect(runCommandMock).toHaveBeenCalledTimes(2);

    act(() => {
      nth(1).resolve([INVESTIGATION]);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.investigations).toEqual([INVESTIGATION]);
  });
});

describe("Strict Mode double-invocation", () => {
  it("only applies the surviving invocation's settlement, never the discarded one's", async () => {
    render(true);

    // Strict Mode mounts twice -- two real runCommand calls fire.
    expect(runCommandMock).toHaveBeenCalledTimes(2);

    // Resolve the discarded (first) invocation's call with different
    // data than the surviving (second) one -- if the discarded
    // settlement were ever applied, this assertion would catch it.
    act(() => {
      nth(0).resolve([INVESTIGATION_2]);
    });
    await act(async () => {
      await flush();
    });

    act(() => {
      nth(1).resolve([INVESTIGATION]);
    });
    await act(async () => {
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.investigations).toEqual([INVESTIGATION]);
  });
});
