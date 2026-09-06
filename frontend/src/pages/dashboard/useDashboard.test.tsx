// @vitest-environment jsdom
import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return { ...actual, runCommand: (...args: unknown[]) => runCommandMock(...args) };
});

import { CommandFailedError } from "../../shared/api/client";
import { useDashboard, type UseDashboardResult } from "./useDashboard";
import type { DashboardSummaryResult } from "../../shared/api/types";

const SUMMARY: DashboardSummaryResult = {
  metrics: {
    total_reports: 3,
    total_iocs: 12,
    high_risk_count: 2,
    threat_intel_coverage_percent: 75,
  },
  investigation_status_counts: { COMPLETED: 3 },
  risk_distribution: { LOW: 1, HIGH: 2 },
  ioc_distribution: { ipv4: 5, domains: 7 },
  recent_investigations: [],
};

interface DeferredCall {
  promise: Promise<unknown>;
  resolve: (value: unknown) => void;
  reject: (error: unknown) => void;
}

function deferred(): DeferredCall {
  let resolve!: (value: unknown) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<unknown>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

let calls: DeferredCall[];
let root: Root;
let container: HTMLDivElement;
let latest!: UseDashboardResult;

function Probe() {
  const result = useDashboard();
  latest = result;
  return <div>{result.state}</div>;
}

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

beforeEach(() => {
  calls = [];
  runCommandMock.mockReset();
  runCommandMock.mockImplementation(() => {
    const call = deferred();
    calls.push(call);
    return call.promise;
  });
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  act(() => root?.unmount());
  container.remove();
});

function render(strict = false): void {
  act(() => {
    root = createRoot(container);
    root.render(strict ? <StrictMode><Probe /></StrictMode> : <Probe />);
  });
}

describe("useDashboard", () => {
  it("starts loading and invokes exactly the aggregate command", () => {
    render();
    expect(latest.state).toBe("loading");
    expect(latest.dashboard).toBeNull();
    expect(runCommandMock).toHaveBeenCalledTimes(1);
    expect(runCommandMock).toHaveBeenCalledWith("get_dashboard_summary", {});
  });

  it("applies a successful DashboardSummaryResult without transformation", async () => {
    render();
    act(() => calls[0]!.resolve(SUMMARY));
    await act(async () => await flush());
    expect(latest.state).toBe("success");
    expect(latest.dashboard).toEqual(SUMMARY);
    expect(latest.error).toBeNull();
  });

  it("preserves a command error and exposes error state", async () => {
    render();
    const failure = new CommandFailedError("get_dashboard_summary", "DATABASE_ERROR", "database unavailable");
    act(() => calls[0]!.reject(failure));
    await act(async () => await flush());
    expect(latest.state).toBe("error");
    expect(latest.dashboard).toBeNull();
    expect(latest.error).toBe(failure);
  });

  it("retries with a fresh command and clears the previous error", async () => {
    render();
    act(() => calls[0]!.reject(new Error("first failure")));
    await act(async () => await flush());
    expect(latest.state).toBe("error");

    act(() => latest.retry());
    expect(latest.state).toBe("loading");
    expect(latest.dashboard).toBeNull();
    expect(runCommandMock).toHaveBeenCalledTimes(2);
    expect(runCommandMock).toHaveBeenNthCalledWith(2, "get_dashboard_summary", {});

    act(() => calls[1]!.resolve(SUMMARY));
    await act(async () => await flush());
    expect(latest.state).toBe("success");
    expect(latest.dashboard).toEqual(SUMMARY);
  });

  it("does not publish a stale response after retry", async () => {
    render();
    act(() => latest.retry());
    expect(runCommandMock).toHaveBeenCalledTimes(2);

    act(() => calls[1]!.resolve(SUMMARY));
    await act(async () => await flush());
    expect(latest.dashboard).toEqual(SUMMARY);

    act(() => calls[0]!.resolve({ ...SUMMARY, metrics: { ...SUMMARY.metrics, total_reports: 999 } }));
    await act(async () => await flush());
    expect(latest.dashboard?.metrics.total_reports).toBe(3);
  });

  it("does not publish a settled request after unmount", async () => {
    render();
    act(() => root.unmount());
    act(() => calls[0]!.resolve(SUMMARY));
    await act(async () => await flush());
    expect(runCommandMock).toHaveBeenCalledTimes(1);
  });

  it("does not let Strict Mode's discarded request publish stale state", async () => {
    render(true);
    expect(runCommandMock).toHaveBeenCalledTimes(2);
    act(() => calls[0]!.resolve({ ...SUMMARY, metrics: { ...SUMMARY.metrics, total_reports: 999 } }));
    await act(async () => await flush());
    expect(latest.state).toBe("loading");
    act(() => calls[1]!.resolve(SUMMARY));
    await act(async () => await flush());
    expect(latest.state).toBe("success");
    expect(latest.dashboard?.metrics.total_reports).toBe(3);
  });
});
