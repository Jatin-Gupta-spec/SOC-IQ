// @vitest-environment jsdom
/**
 * Live-DOM tests for `useInvestigation` — follows the same
 * `react-dom/client` + `act` approach `useAnalysisExecution.test.tsx`
 * / `useSidecarStatus.test.tsx` already established (no
 * `@testing-library/react` added as a second dependency). Needed here
 * for the same reason those files give: real effect timing, real
 * `Promise.allSettled()` microtask ordering, and Strict Mode's
 * mount→cleanup→mount double-invocation are exactly what's under
 * test.
 *
 * `runCommand` is mocked at its own module boundary
 * (`../../shared/api/client`), mirroring
 * `analysisExecution.test.ts`'s established pattern (`vi.mock` with
 * `importActual` to keep the real `CommandFailedError` /
 * `CommandNetworkError` classes usable in fixtures) — this hook's own
 * fetch/state-machine logic is what's tested, never a fake successful
 * backend call mistaken for integration testing.
 *
 * A4-P2-P3 Part 5A added `get_timeline` as a fourth parallel request
 * (`nth(3)` in every cycle below). PD-08-P2 adds
 * `get_investigation_risk_explanation` as a fifth parallel request
 * (`nth(4)`), following the exact same pattern `get_timeline` itself
 * established -- every existing investigation/IOC/threat-intelligence/
 * timeline assertion is preserved unchanged in substance; only the
 * call-count/position bookkeeping that a fifth request affects has
 * been updated, plus new coverage for the risk-explanation request
 * itself.
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
import { useInvestigation } from "./useInvestigation";
import type { UseInvestigationResult } from "./useInvestigation";
import type {
  GetInvestigationResult,
  GetInvestigationRiskExplanationResult,
  GetIocsResult,
  GetThreatIntelligenceResult,
  GetTimelineResult,
} from "../../shared/api/types";

const INVESTIGATION: GetInvestigationResult = {
  investigation_id: 7,
  report_name: "report.txt",
  risk_score: 42,
  severity: "high",
  confidence: 0.9,
  status: "complete",
  analyzed_at: "2026-08-26T00:00:00",
  correlations: [],
};

const INVESTIGATION_2: GetInvestigationResult = {
  investigation_id: 9,
  report_name: "second-report.txt",
  risk_score: 12,
  severity: "low",
  confidence: 0.5,
  status: "complete",
  analyzed_at: "2026-08-26T01:00:00",
  correlations: [],
};

const IOCS_RESULT: GetIocsResult = {
  investigation_id: 7,
  iocs: { ipv4: ["1.2.3.4"] },
  significance: { ipv4: { weight: 8, significance: "High" } },
};

const TI_RESULT: GetThreatIntelligenceResult = {
  investigation_id: 7,
  threat_intelligence: { "1.2.3.4": { vendor: "vt", malicious: 3, opaque_nested: { a: 1 } } },
  states: { ipv4: { "1.2.3.4": "enriched" } },
};

const TIMELINE_RESULT: GetTimelineResult = {
  investigation_id: 7,
  events: [
    {
      event_id: "evt-1",
      investigation_id: 7,
      event_type: "investigation.created",
      timestamp: "2026-08-26T00:00:00",
      source: "system",
      summary: "Investigation created.",
      metadata: {},
      semantics: "SOC-IQ created this investigation record.",
    },
  ],
};

const RISK_EXPLANATION_RESULT: GetInvestigationRiskExplanationResult = {
  investigation_id: 7,
  report_name: "report.txt",
  score: 42,
  severity: "high",
  confidence: 0.9,
  ioc_score: 30,
  threat_intel_score: 10,
  cve_score: 2,
  ioc_categories: [
    {
      ioc_type: "ipv4",
      ioc_type_title: "IP Addresses",
      count: 1,
      weight: 30,
      significance: "high",
      points: 30,
    },
  ],
  ioc_breakdown_verified: true,
  threat_intel_state: "enriched",
  threat_intel_message: "Threat intelligence was checked for available indicators.",
  threat_intel_short_label: "Enriched",
  threat_intel_requested: 1,
  threat_intel_succeeded: 1,
  threat_intel_malicious_hash_count: 0,
  threat_intel_suspicious_hash_count: 0,
  correlation_evaluated: true,
  correlation_relationship_count: 0,
  correlation_summary: "No explicit correlations were found.",
  engine_reasons: [],
  narrative: ["This investigation scored 42 (high) based on 1 IP address indicator."],
  warnings: [],
};

const EMPTY_DATA_SHAPE = {
  investigation: null,
  iocs: null,
  iocSignificance: null,
  threatIntelligence: null,
  timeline: null,
  riskExplanation: null,
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

/** Resolves the standard five-call successful cycle (investigation,
 * iocs, threat intel, timeline, risk explanation) at the given base
 * index -- the pattern nearly every test below uses, now that a fifth
 * parallel request exists. */
function resolveAllAt(base: number): void {
  nth(base).resolve(INVESTIGATION);
  nth(base + 1).resolve(IOCS_RESULT);
  nth(base + 2).resolve(TI_RESULT);
  nth(base + 3).resolve(TIMELINE_RESULT);
  nth(base + 4).resolve(RISK_EXPLANATION_RESULT);
}

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

let container: HTMLDivElement;
let root: Root;
let latestResult: UseInvestigationResult;

function Probe({ investigationId, strict = false }: { investigationId: number; strict?: boolean }) {
  return strict ? (
    <StrictMode>
      <ProbeInner investigationId={investigationId} />
    </StrictMode>
  ) : (
    <ProbeInner investigationId={investigationId} />
  );
}

function ProbeInner({ investigationId }: { investigationId: number }) {
  latestResult = useInvestigation(investigationId);
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

function render(investigationId: number, strict = false): void {
  act(() => {
    root = createRoot(container);
    root.render(<Probe investigationId={investigationId} strict={strict} />);
  });
}

function rerender(investigationId: number, strict = false): void {
  act(() => {
    root.render(<Probe investigationId={investigationId} strict={strict} />);
  });
}

describe("initial state", () => {
  it("starts in loading state with no data for a valid investigationId", () => {
    render(7);

    expect(latestResult.state).toBe("loading");
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);
    expect(latestResult.investigationError).toBeNull();
    expect(latestResult.iocsError).toBeNull();
    expect(latestResult.threatIntelligenceError).toBeNull();
    expect(latestResult.timelineError).toBeNull();
    expect(latestResult.riskExplanationError).toBeNull();
  });

  it("issues all five commands with the given investigationId", () => {
    render(7);

    expect(runCommandMock).toHaveBeenCalledTimes(5);
    expect(runCommandMock).toHaveBeenNthCalledWith(1, "get_investigation", { investigation_id: 7 });
    expect(runCommandMock).toHaveBeenNthCalledWith(2, "get_iocs", { investigation_id: 7 });
    expect(runCommandMock).toHaveBeenNthCalledWith(3, "get_threat_intelligence", {
      investigation_id: 7,
    });
    expect(runCommandMock).toHaveBeenNthCalledWith(4, "get_timeline", { investigation_id: 7 });
    expect(runCommandMock).toHaveBeenNthCalledWith(5, "get_investigation_risk_explanation", {
      investigation_id: 7,
    });
  });

  it("issues the five requests in parallel (all five fire before any settles)", () => {
    render(7);

    // All five calls already happened synchronously within the same
    // effect pass -- none is gated behind another's resolution.
    expect(runCommandMock).toHaveBeenCalledTimes(5);
    expect(callDeferreds).toHaveLength(5);
  });
});

describe("successful load", () => {
  it("resolves to success with all five results applied", async () => {
    render(7);

    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.data.iocs).toEqual(IOCS_RESULT.iocs);
    expect(latestResult.data.iocSignificance).toEqual(IOCS_RESULT.significance);
    expect(latestResult.data.threatIntelligence).toEqual({
      raw: TI_RESULT.threat_intelligence,
      states: TI_RESULT.states,
    });
    expect(latestResult.data.timeline).toEqual(TIMELINE_RESULT.events);
    expect(latestResult.data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);
    expect(latestResult.investigationError).toBeNull();
    expect(latestResult.iocsError).toBeNull();
    expect(latestResult.threatIntelligenceError).toBeNull();
    expect(latestResult.timelineError).toBeNull();
    expect(latestResult.riskExplanationError).toBeNull();
  });

  it("keeps the raw threat_intelligence payload byte-for-byte intact, including opaque nested fields", async () => {
    render(7);

    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.data.threatIntelligence?.raw).toEqual(TI_RESULT.threat_intelligence);
  });

  it("keeps the TI_STATE_* states projection intact", async () => {
    render(7);

    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.data.threatIntelligence?.states).toEqual(TI_RESULT.states);
  });

  it("applies get_timeline's events as the hook's timeline data, in the order returned", async () => {
    render(7);

    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.data.timeline).toEqual(TIMELINE_RESULT.events);
    expect(latestResult.timelineError).toBeNull();
  });

  it("applies get_investigation_risk_explanation's result as the hook's riskExplanation data, unchanged", async () => {
    render(7);

    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);
    expect(latestResult.riskExplanationError).toBeNull();
  });
});

describe("investigation not found", () => {
  it("resolves to notFound on an INVESTIGATION_NOT_FOUND failure, regardless of the other four", async () => {
    render(7);
    const notFoundError = new CommandFailedError(
      "get_investigation",
      "INVESTIGATION_NOT_FOUND",
      "No investigation with that id.",
    );

    await act(async () => {
      nth(0).reject(notFoundError);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("notFound");
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);
    expect(latestResult.investigationError).toBe(notFoundError);
  });
});

describe("investigation generic failure", () => {
  it("resolves to error on any other investigation failure", async () => {
    render(7);
    const networkError = new CommandNetworkError("get_investigation", new Error("offline"));

    await act(async () => {
      nth(0).reject(networkError);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("error");
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);
    expect(latestResult.investigationError).toBe(networkError);
  });

  it("resolves to error (not notFound) for a CommandFailedError with a different code", async () => {
    render(7);
    const validationError = new CommandFailedError(
      "get_investigation",
      "INVALID_COMMAND_PAYLOAD",
      "Bad payload.",
    );

    await act(async () => {
      nth(0).reject(validationError);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("error");
  });
});

describe("partial failure", () => {
  it("resolves to partial when only the IOC fetch fails, keeping investigation, TI, timeline, and risk explanation data", async () => {
    render(7);
    const iocsError = new CommandNetworkError("get_iocs", new Error("timeout"));

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).reject(iocsError);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("partial");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.data.iocs).toBeNull();
    // Derived from the same rejected `get_iocs` settlement as `iocs`
    // above -- a failed IOC fetch must never leave a stale/fabricated
    // significance map behind (see `UseInvestigationData
    // .iocSignificance`'s own doc comment).
    expect(latestResult.data.iocSignificance).toBeNull();
    expect(latestResult.data.threatIntelligence).toEqual({
      raw: TI_RESULT.threat_intelligence,
      states: TI_RESULT.states,
    });
    expect(latestResult.data.timeline).toEqual(TIMELINE_RESULT.events);
    expect(latestResult.data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);
    expect(latestResult.iocsError).toBe(iocsError);
    expect(latestResult.threatIntelligenceError).toBeNull();
    expect(latestResult.timelineError).toBeNull();
    expect(latestResult.riskExplanationError).toBeNull();
  });

  it("resolves to partial when only the TI fetch fails, keeping investigation, IOC, timeline, and risk explanation data", async () => {
    render(7);
    const tiError = new CommandNetworkError("get_threat_intelligence", new Error("timeout"));

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).reject(tiError);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("partial");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.data.iocs).toEqual(IOCS_RESULT.iocs);
    expect(latestResult.data.iocSignificance).toEqual(IOCS_RESULT.significance);
    expect(latestResult.data.threatIntelligence).toBeNull();
    expect(latestResult.data.timeline).toEqual(TIMELINE_RESULT.events);
    expect(latestResult.data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);
    expect(latestResult.iocsError).toBeNull();
    expect(latestResult.threatIntelligenceError).toBe(tiError);
    expect(latestResult.timelineError).toBeNull();
    expect(latestResult.riskExplanationError).toBeNull();
  });

  it("resolves to partial when only the timeline fetch fails, keeping investigation, IOC, TI, and risk explanation data", async () => {
    render(7);
    const timelineError = new CommandNetworkError("get_timeline", new Error("timeout"));

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).reject(timelineError);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("partial");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.data.iocs).toEqual(IOCS_RESULT.iocs);
    expect(latestResult.data.iocSignificance).toEqual(IOCS_RESULT.significance);
    expect(latestResult.data.threatIntelligence).toEqual({
      raw: TI_RESULT.threat_intelligence,
      states: TI_RESULT.states,
    });
    expect(latestResult.data.timeline).toBeNull();
    expect(latestResult.data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);
    expect(latestResult.iocsError).toBeNull();
    expect(latestResult.threatIntelligenceError).toBeNull();
    expect(latestResult.timelineError).toBe(timelineError);
    expect(latestResult.riskExplanationError).toBeNull();
  });

  it("resolves to partial when only the risk explanation fetch fails, keeping investigation, IOC, TI, and timeline data", async () => {
    render(7);
    const riskExplanationError = new CommandNetworkError(
      "get_investigation_risk_explanation",
      new Error("timeout"),
    );

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).reject(riskExplanationError);
      await flush();
    });

    expect(latestResult.state).toBe("partial");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.data.iocs).toEqual(IOCS_RESULT.iocs);
    expect(latestResult.data.iocSignificance).toEqual(IOCS_RESULT.significance);
    expect(latestResult.data.threatIntelligence).toEqual({
      raw: TI_RESULT.threat_intelligence,
      states: TI_RESULT.states,
    });
    expect(latestResult.data.timeline).toEqual(TIMELINE_RESULT.events);
    expect(latestResult.data.riskExplanation).toBeNull();
    expect(latestResult.iocsError).toBeNull();
    expect(latestResult.threatIntelligenceError).toBeNull();
    expect(latestResult.timelineError).toBeNull();
    expect(latestResult.riskExplanationError).toBe(riskExplanationError);
  });

  it("resolves to partial with all errors distinctly represented when IOCs, TI, timeline, and risk explanation all fail", async () => {
    render(7);
    const iocsError = new CommandNetworkError("get_iocs", new Error("timeout"));
    const tiError = new CommandNetworkError("get_threat_intelligence", new Error("timeout"));
    const timelineError = new CommandNetworkError("get_timeline", new Error("timeout"));
    const riskExplanationError = new CommandNetworkError(
      "get_investigation_risk_explanation",
      new Error("timeout"),
    );

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).reject(iocsError);
      nth(2).reject(tiError);
      nth(3).reject(timelineError);
      nth(4).reject(riskExplanationError);
      await flush();
    });

    expect(latestResult.state).toBe("partial");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
    expect(latestResult.iocsError).toBe(iocsError);
    expect(latestResult.threatIntelligenceError).toBe(tiError);
    expect(latestResult.timelineError).toBe(timelineError);
    expect(latestResult.riskExplanationError).toBe(riskExplanationError);
  });

  it("never represents a failed IOC fetch as an empty IOC list", async () => {
    render(7);

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).reject(new CommandNetworkError("get_iocs", new Error("timeout")));
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.data.iocs).toBeNull();
    expect(latestResult.data.iocs).not.toEqual({});
  });

  it("never represents a failed TI fetch as empty TI data", async () => {
    render(7);

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).reject(new CommandNetworkError("get_threat_intelligence", new Error("timeout")));
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.data.threatIntelligence).toBeNull();
  });

  it("never represents a failed timeline fetch as an empty timeline list", async () => {
    render(7);

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).reject(new CommandNetworkError("get_timeline", new Error("timeout")));
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.data.timeline).toBeNull();
    expect(latestResult.data.timeline).not.toEqual([]);
  });

  it("never represents a failed risk explanation fetch as a fabricated explanation", async () => {
    render(7);

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).reject(new CommandNetworkError("get_investigation_risk_explanation", new Error("timeout")));
      await flush();
    });

    expect(latestResult.data.riskExplanation).toBeNull();
  });
});

describe("retry", () => {
  it("starts a fresh request cycle and recovers from an error", async () => {
    render(7);

    await act(async () => {
      nth(0).reject(new CommandNetworkError("get_investigation", new Error("offline")));
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });
    expect(latestResult.state).toBe("error");

    act(() => {
      latestResult.retry();
    });

    expect(latestResult.state).toBe("loading");
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);
    expect(runCommandMock).toHaveBeenCalledTimes(10);

    await act(async () => {
      resolveAllAt(5);
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
  });

  it("starts a fresh request cycle and recovers from partial failure, clearing the stale sub-errors", async () => {
    render(7);

    await act(async () => {
      nth(0).resolve(INVESTIGATION);
      nth(1).reject(new CommandNetworkError("get_iocs", new Error("timeout")));
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });
    expect(latestResult.state).toBe("partial");

    act(() => {
      latestResult.retry();
    });
    // Retry does not retain stale partial data across the reset --
    // "prefer predictable behavior over clever caching".
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);

    await act(async () => {
      resolveAllAt(5);
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.iocsError).toBeNull();
  });
});

describe("stale response protection", () => {
  it("does not let a late response for a superseded investigationId overwrite the current one", async () => {
    render(7);
    expect(runCommandMock).toHaveBeenCalledTimes(5);

    rerender(9);
    expect(runCommandMock).toHaveBeenCalledTimes(10);

    // The new (id 9) cycle resolves first...
    await act(async () => {
      nth(5).resolve(INVESTIGATION_2);
      nth(6).resolve({ investigation_id: 9, iocs: {} });
      nth(7).resolve({ investigation_id: 9, threat_intelligence: {}, states: {} });
      nth(8).resolve({ investigation_id: 9, events: [] });
      nth(9).resolve({ ...RISK_EXPLANATION_RESULT, investigation_id: 9 });
      await flush();
    });
    expect(latestResult.state).toBe("success");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION_2);

    // ...then the stale (id 7) cycle resolves late. It must be ignored.
    await act(async () => {
      resolveAllAt(0);
      await flush();
    });

    expect(latestResult.state).toBe("success");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION_2);
  });

  it("does not let a late pre-retry response overwrite the post-retry cycle", async () => {
    render(7);

    act(() => {
      latestResult.retry();
    });
    expect(runCommandMock).toHaveBeenCalledTimes(10);

    // The retry cycle resolves first...
    await act(async () => {
      resolveAllAt(5);
      await flush();
    });
    expect(latestResult.state).toBe("success");

    // ...then the stale pre-retry cycle resolves late with a failure.
    // It must not flip a successful, newer state back to an error.
    await act(async () => {
      nth(0).reject(new CommandNetworkError("get_investigation", new Error("offline")));
      nth(1).resolve(IOCS_RESULT);
      nth(2).resolve(TI_RESULT);
      nth(3).resolve(TIMELINE_RESULT);
      nth(4).resolve(RISK_EXPLANATION_RESULT);
      await flush();
    });

    expect(latestResult.state).toBe("success");
  });
});

describe("unmount safety", () => {
  it("does not throw or apply state when the component unmounts while requests are pending", async () => {
    render(7);

    act(() => {
      root.unmount();
    });

    // Resolving after unmount must not throw ("setState after unmount")
    // and, since the component tree is gone, has nothing to observe --
    // the point is purely that this does not throw.
    await expect(
      act(async () => {
        resolveAllAt(0);
        await flush();
      }),
    ).resolves.not.toThrow();

    // Re-create the root so the shared afterEach's root.unmount() call
    // has a live root to operate on.
    act(() => {
      root = createRoot(container);
    });
  });
});

describe("invalid investigationId", () => {
  it("does not call the backend and reports idle for a zero id", () => {
    render(0);

    expect(runCommandMock).not.toHaveBeenCalled();
    expect(latestResult.state).toBe("idle");
    expect(latestResult.data).toEqual(EMPTY_DATA_SHAPE);
  });

  it("does not call the backend for a negative id", () => {
    render(-1);

    expect(runCommandMock).not.toHaveBeenCalled();
    expect(latestResult.state).toBe("idle");
  });

  it("does not call the backend for a non-integer id", () => {
    render(1.5);

    expect(runCommandMock).not.toHaveBeenCalled();
    expect(latestResult.state).toBe("idle");
  });
});

describe("duplicate request protection", () => {
  it("does not fire a second request cycle on a re-render with the same investigationId", () => {
    render(7);
    expect(runCommandMock).toHaveBeenCalledTimes(5);

    rerender(7);

    expect(runCommandMock).toHaveBeenCalledTimes(5);
  });

  it("Strict Mode's discarded first invocation never has its results applied", async () => {
    render(7, /* strict */ true);

    // Strict Mode double-invokes the effect in dev: two cycles fire
    // (10 calls), but only the surviving invocation's generation may
    // ever be applied.
    expect(runCommandMock).toHaveBeenCalledTimes(10);

    await act(async () => {
      // Resolve the discarded (first) cycle only.
      resolveAllAt(0);
      await flush();
    });
    // The discarded cycle's own cleanup ran before it could settle
    // from this hook's perspective (cancelled=true), so it must not
    // have moved state to success by itself.
    expect(latestResult.state).not.toBe("success");

    await act(async () => {
      // Resolve the surviving (second) cycle.
      resolveAllAt(5);
      await flush();
    });
    expect(latestResult.state).toBe("success");
    expect(latestResult.data.investigation).toEqual(INVESTIGATION);
  });
});
