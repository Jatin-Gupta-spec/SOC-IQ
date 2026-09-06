// @vitest-environment jsdom
/**
 * Cross-module analyst journey integration test (MAX-20B).
 *
 * MAX-20A found every individual hook in this journey (`executeAnalysis`,
 * `useInvestigation`, `useReportExport`) thoroughly tested in isolation, each
 * with its own independently-scoped `runCommand` mock -- but no test drives
 * the *real, composed* sequence a working analyst actually performs:
 *
 *   1. Analyze a report            -> analyze_report
 *   2. Open the Investigation
 *      Workspace for that id       -> get_investigation / get_iocs /
 *                                     get_threat_intelligence / get_timeline /
 *                                     get_investigation_risk_explanation
 *   3. Export the report           -> export_report
 *   4. Navigate away and reopen
 *      the same investigation
 *      from history                -> the same five workspace reads again
 *
 * This file closes exactly that gap. It imports the real, unmodified
 * `executeAnalysis`, `useInvestigation`, and `useReportExport` modules and
 * drives them against a single shared `runCommand` mock -- the same seam
 * every other test in this codebase already mocks at (see
 * `useInvestigation.test.tsx`, `useReportExport.test.tsx`,
 * `analysisExecution.test.ts`). No application behavior is changed by this
 * file; it only adds coverage for an invariant nothing else asserts:
 * **`analyze_report` is called exactly once for the whole journey**, even
 * across opening the workspace, exporting, retrying a failed export, and
 * reopening the investigation later from history. No test elsewhere in the
 * suite makes that specific cross-stage assertion.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const runCommandMock = vi.fn();
const pickReportSavePathMock = vi.fn();

vi.mock("../../shared/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/client")>(
    "../../shared/api/client",
  );
  return {
    ...actual,
    runCommand: (...args: unknown[]) => runCommandMock(...args),
  };
});

vi.mock("../reports/reportExportPath", () => ({
  pickReportSavePath: (...args: unknown[]) => pickReportSavePathMock(...args),
}));

import { CommandFailedError } from "../../shared/api/client";
import { executeAnalysis } from "../analyze/analysisExecution";
import { DEFAULT_ANALYSIS_OPTIONS } from "../analyze/analysisWorkflowState";
import { useInvestigation } from "./useInvestigation";
import type { UseInvestigationResult } from "./useInvestigation";
import { useReportExport } from "../reports/useReportExport";
import type { UseReportExportResult } from "../reports/useReportExport";
import type {
  AnalyzeReportResult,
  GetInvestigationResult,
  GetInvestigationRiskExplanationResult,
  GetIocsResult,
  GetThreatIntelligenceResult,
  GetTimelineResult,
} from "../../shared/api/types";

const INVESTIGATION_ID = 42;

const INVESTIGATION: GetInvestigationResult = {
  investigation_id: INVESTIGATION_ID,
  report_name: "malware_report.txt",
  risk_score: 77,
  severity: "high",
  confidence: 0.95,
  status: "complete",
  analyzed_at: "2026-09-06T00:00:00",
  correlations: [],
};

const ANALYZE_RESULT: AnalyzeReportResult = {
  correlation_id: "corr-1",
  investigation: INVESTIGATION,
  existing: false,
  options: DEFAULT_ANALYSIS_OPTIONS,
};

const IOCS_RESULT: GetIocsResult = {
  investigation_id: INVESTIGATION_ID,
  iocs: { ipv4: ["10.0.0.1"] },
  significance: { ipv4: { weight: 8, significance: "High" } },
};

const TI_RESULT: GetThreatIntelligenceResult = {
  investigation_id: INVESTIGATION_ID,
  threat_intelligence: { "10.0.0.1": { vendor: "vt", malicious: 5 } },
  states: { ipv4: { "10.0.0.1": "enriched" } },
};

const TIMELINE_RESULT: GetTimelineResult = {
  investigation_id: INVESTIGATION_ID,
  events: [
    {
      event_id: "evt-1",
      investigation_id: INVESTIGATION_ID,
      event_type: "investigation.created",
      timestamp: "2026-09-06T00:00:00",
      source: "system",
      summary: "Investigation created.",
      metadata: {},
      semantics: "SOC-IQ created this investigation record.",
    },
  ],
};

const RISK_EXPLANATION_RESULT: GetInvestigationRiskExplanationResult = {
  investigation_id: INVESTIGATION_ID,
  report_name: "malware_report.txt",
  score: 77,
  severity: "high",
  confidence: 0.95,
  ioc_score: 50,
  threat_intel_score: 25,
  cve_score: 2,
  ioc_categories: [
    {
      ioc_type: "ipv4",
      ioc_type_title: "IP Addresses",
      count: 1,
      weight: 50,
      significance: "high",
      points: 50,
    },
  ],
  ioc_breakdown_verified: true,
  threat_intel_state: "enriched",
  threat_intel_message: "Threat intelligence was checked for available indicators.",
  threat_intel_short_label: "Enriched",
  threat_intel_requested: 1,
  threat_intel_succeeded: 1,
  threat_intel_malicious_hash_count: 1,
  threat_intel_suspicious_hash_count: 0,
  correlation_evaluated: true,
  correlation_relationship_count: 0,
  correlation_summary: "No explicit correlations were found.",
  engine_reasons: [],
  narrative: ["This investigation scored 77 (high) based on 1 IP address indicator."],
  warnings: [],
};

/** Resolves whichever `runCommand` call matches `name`, in call order,
 * without assuming the five workspace reads fire in a fixed relative
 * order (they're started via `Promise.allSettled`). */
function resolveByName(name: string, value: unknown): void {
  const callIndex = runCommandMock.mock.calls.findIndex(
    (call, index) => call[0] === name && !resolvedIndices.has(index),
  );
  if (callIndex === -1) {
    throw new Error(`No pending runCommand("${name}", ...) call found to resolve.`);
  }
  resolvedIndices.add(callIndex);
  pendingResolvers[callIndex]!(value);
}

let resolvedIndices: Set<number>;
let pendingResolvers: Array<(value: unknown) => void>;

function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function openWorkspace(investigationId: number): Promise<{
  root: Root;
  container: HTMLDivElement;
  getResult: () => UseInvestigationResult;
}> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let latest!: UseInvestigationResult;

  function Probe() {
    latest = useInvestigation(investigationId);
    return null;
  }

  let root!: Root;
  act(() => {
    root = createRoot(container);
    root.render(<Probe />);
  });

  // Let the five parallel workspace reads fire, then resolve them all
  // successfully, matching a healthy Investigation Workspace open.
  await flush();
  act(() => {
    resolveByName("get_investigation", INVESTIGATION);
    resolveByName("get_iocs", IOCS_RESULT);
    resolveByName("get_threat_intelligence", TI_RESULT);
    resolveByName("get_timeline", TIMELINE_RESULT);
    resolveByName("get_investigation_risk_explanation", RISK_EXPLANATION_RESULT);
  });
  await flush();

  return { root, container, getResult: () => latest };
}

beforeEach(() => {
  runCommandMock.mockReset();
  pickReportSavePathMock.mockReset();
  resolvedIndices = new Set();
  pendingResolvers = [];
  runCommandMock.mockImplementation(() => {
    return new Promise((resolve) => {
      pendingResolvers.push(resolve as (value: unknown) => void);
    });
  });
});

describe("full analyst journey: analyze -> workspace -> export -> reopen", () => {
  it("carries the same investigation id through every stage and creates exactly one investigation", async () => {
    // 1. Select a file & analyze.
    const analyzePromise = executeAnalysis("/reports/malware_report.txt", DEFAULT_ANALYSIS_OPTIONS);
    await flush();
    act(() => {
      resolveByName("analyze_report", ANALYZE_RESULT);
    });
    const analyzeOutcome = await analyzePromise;

    expect(analyzeOutcome.ok).toBe(true);
    if (!analyzeOutcome.ok) throw new Error("expected success");
    const investigationId = analyzeOutcome.result.investigationId;
    if (investigationId === null) throw new Error("expected a non-null investigationId");
    expect(investigationId).toBe(INVESTIGATION_ID);

    // 2. Open the Investigation Workspace for the id analyze just returned --
    // findings, risk, threat intel, timeline, and IOCs all present together.
    const workspace = await openWorkspace(investigationId);
    expect(workspace.getResult().state).toBe("success");
    expect(workspace.getResult().data.investigation?.investigation_id).toBe(investigationId);
    expect(workspace.getResult().data.iocs).not.toBeNull();
    expect(workspace.getResult().data.threatIntelligence).not.toBeNull();
    expect(workspace.getResult().data.timeline).not.toBeNull();
    expect(workspace.getResult().data.riskExplanation?.score).toBe(77);

    // 3. Export the report for this same investigation.
    let exportLatest!: UseReportExportResult;
    const exportContainer = document.createElement("div");
    document.body.appendChild(exportContainer);
    function ExportProbe() {
      exportLatest = useReportExport();
      return null;
    }
    let exportRoot!: Root;
    act(() => {
      exportRoot = createRoot(exportContainer);
      exportRoot.render(<ExportProbe />);
    });

    pickReportSavePathMock.mockResolvedValueOnce({ ok: true, path: "/tmp/malware_report.html", format: "html" });
    act(() => {
      exportLatest.runExport(investigationId, "malware_report");
    });
    await flush();
    act(() => {
      resolveByName("export_report", {
        investigation_id: investigationId,
        export_format: "html",
        output_path: "/tmp/malware_report.html",
      });
    });
    await flush();

    expect(exportLatest.state).toEqual({ status: "success", outputPath: "/tmp/malware_report.html" });

    // 4. Navigate away (unmount) and reopen the same investigation from
    // history -- a fresh workspace mount, simulating the analyst leaving
    // Investigations and clicking back into this row later.
    act(() => {
      workspace.root.unmount();
    });
    workspace.container.remove();

    const reopened = await openWorkspace(investigationId);
    expect(reopened.getResult().state).toBe("success");
    // State preserved: reopening returns the same investigation data, not a
    // different or partially-hydrated view.
    expect(reopened.getResult().data.investigation).toEqual(INVESTIGATION);
    expect(reopened.getResult().data.riskExplanation).toEqual(RISK_EXPLANATION_RESULT);

    act(() => {
      reopened.root.unmount();
    });
    reopened.container.remove();
    act(() => {
      exportRoot.unmount();
    });
    exportContainer.remove();

    // Invariant: across analyze + first open + export + reopen, exactly one
    // analyze_report call ever happened -- opening, exporting, and
    // reopening the workspace never create a second investigation.
    const analyzeCalls = runCommandMock.mock.calls.filter((call) => call[0] === "analyze_report");
    expect(analyzeCalls).toHaveLength(1);
  });

  it("recovers from a failed export via retry without creating a duplicate investigation or losing workspace state", async () => {
    const analyzePromise = executeAnalysis("/reports/report.txt", DEFAULT_ANALYSIS_OPTIONS);
    await flush();
    act(() => {
      resolveByName("analyze_report", ANALYZE_RESULT);
    });
    const analyzeOutcome = await analyzePromise;
    if (!analyzeOutcome.ok) throw new Error("expected success");
    const investigationId = analyzeOutcome.result.investigationId;
    if (investigationId === null) throw new Error("expected a non-null investigationId");

    const workspace = await openWorkspace(investigationId);
    expect(workspace.getResult().state).toBe("success");

    let exportLatest!: UseReportExportResult;
    const exportContainer = document.createElement("div");
    document.body.appendChild(exportContainer);
    function ExportProbe() {
      exportLatest = useReportExport();
      return null;
    }
    let exportRoot!: Root;
    act(() => {
      exportRoot = createRoot(exportContainer);
      exportRoot.render(<ExportProbe />);
    });

    // First export attempt fails with an understandable, typed error.
    pickReportSavePathMock.mockResolvedValueOnce({ ok: true, path: "/tmp/report.html", format: "html" });
    act(() => {
      exportLatest.runExport(investigationId, "report");
    });
    await flush();
    act(() => {
      const callIndex = runCommandMock.mock.calls.findIndex(
        (call, index) => call[0] === "export_report" && !resolvedIndices.has(index),
      );
      resolvedIndices.add(callIndex);
      // Reject rather than resolve -- exercises the error branch.
      pendingResolvers[callIndex]!(
        Promise.reject(new CommandFailedError("export_report", "DISK_FULL", "Not enough disk space.")),
      );
    });
    await flush();
    await flush();

    expect(exportLatest.state.status).toBe("error");

    // Retry succeeds -- no corrupted state, no stuck "exporting" spinner.
    pickReportSavePathMock.mockResolvedValueOnce({ ok: true, path: "/tmp/report.html", format: "html" });
    act(() => {
      exportLatest.runExport(investigationId, "report");
    });
    await flush();
    act(() => {
      resolveByName("export_report", {
        investigation_id: investigationId,
        export_format: "html",
        output_path: "/tmp/report.html",
      });
    });
    await flush();

    expect(exportLatest.state).toEqual({ status: "success", outputPath: "/tmp/report.html" });

    act(() => {
      workspace.root.unmount();
      exportRoot.unmount();
    });
    workspace.container.remove();
    exportContainer.remove();

    // A failed-then-retried export must never have touched analyze_report
    // again -- the failure and retry are scoped entirely to export, not to
    // the investigation's identity.
    const analyzeCalls = runCommandMock.mock.calls.filter((call) => call[0] === "analyze_report");
    expect(analyzeCalls).toHaveLength(1);
    const exportCalls = runCommandMock.mock.calls.filter((call) => call[0] === "export_report");
    expect(exportCalls).toHaveLength(2);
  });
});
