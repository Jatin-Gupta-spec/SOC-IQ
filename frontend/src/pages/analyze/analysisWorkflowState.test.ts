import { describe, expect, it } from "vitest";

import { toAnalysisInput } from "./analysisInput";
import type { AnalysisInputRejection } from "./analysisInput";
import type { AnalysisExecutionError } from "./analysisExecutionError";
import type { AnalysisOptions } from "../../shared/api/types";
import {
  adoptCorrelationId,
  beginExecuting,
  beginValidating,
  DEFAULT_ANALYSIS_OPTIONS,
  initialAnalysisWorkflowState,
  markExecutionCompleted,
  markExecutionFailed,
  markInvalid,
  markReady,
  reset,
  retryFailed,
  selectInput,
  updateOptions,
  updateProgress,
} from "./analysisWorkflowState";
import type { AnalysisExecutionResult, AnalysisReadyState } from "./analysisWorkflowState";

function fixtureInput(name = "report.txt", size = 12): ReturnType<typeof toAnalysisInput> {
  return toAnalysisInput(new File(["x".repeat(size)], name, { type: "text/plain" }));
}

const IOCS_ONLY: AnalysisOptions = { extract_iocs: true, enrich_ti: false, score_risk: false };

describe("initialAnalysisWorkflowState", () => {
  it("starts idle", () => {
    expect(initialAnalysisWorkflowState).toEqual({ status: "idle" });
  });
});

describe("selectInput", () => {
  it("produces an inputSelected state carrying the given input", () => {
    const input = fixtureInput();
    const state = selectInput(input);
    expect(state).toEqual({ status: "inputSelected", input });
  });
});

describe("beginValidating", () => {
  it("carries the same input into validating", () => {
    const input = fixtureInput();
    const selected = selectInput(input);
    const validating = beginValidating(selected);
    expect(validating).toEqual({ status: "validating", input });
  });
});

describe("markReady", () => {
  it("carries the same input into ready", () => {
    const input = fixtureInput();
    const validating = beginValidating(selectInput(input));
    const ready = markReady(validating);
    expect(ready.input).toBe(input);
  });

  it("defaults to every stage selected, matching the server-side default for an omitted options field", () => {
    const ready = markReady(beginValidating(selectInput(fixtureInput())));
    expect(ready.options).toEqual(DEFAULT_ANALYSIS_OPTIONS);
    expect(ready.options).toEqual({ extract_iocs: true, enrich_ti: true, score_risk: true });
  });
});

describe("updateOptions", () => {
  it("replaces the options on a ready state without touching the input", () => {
    const ready = markReady(beginValidating(selectInput(fixtureInput())));
    const updated = updateOptions(ready, IOCS_ONLY);
    expect(updated.options).toEqual(IOCS_ONLY);
    expect(updated.input).toBe(ready.input);
    expect(updated.status).toBe("ready");
  });

  it("is a pure replacement — later calls fully overwrite, not merge, the prior selection", () => {
    const ready = markReady(beginValidating(selectInput(fixtureInput())));
    const first = updateOptions(ready, { extract_iocs: false, enrich_ti: true, score_risk: true });
    const second = updateOptions(first, { extract_iocs: false, enrich_ti: false, score_risk: true });
    expect(second.options).toEqual({ extract_iocs: false, enrich_ti: false, score_risk: true });
  });
});

describe("markInvalid", () => {
  it("carries the input and the rejection into invalid", () => {
    const input = fixtureInput();
    const validating = beginValidating(selectInput(input));
    const rejection: AnalysisInputRejection = { reason: "empty" };
    const invalid = markInvalid(validating, rejection);
    expect(invalid).toEqual({ status: "invalid", input, rejection });
  });
});

describe("reset", () => {
  it("returns to idle", () => {
    expect(reset()).toEqual({ status: "idle" });
  });
});

describe("state shape invariants", () => {
  it("idle never carries an input field", () => {
    expect("input" in initialAnalysisWorkflowState).toBe(false);
  });

  it("ready always carries the input it was validated from", () => {
    const input = fixtureInput("evidence.log", 40);
    const ready = markReady(beginValidating(selectInput(input)));
    expect(ready.input).toBe(input);
  });
});

function fixtureReady(): AnalysisReadyState {
  return markReady(beginValidating(selectInput(fixtureInput())));
}

function fixtureResult(overrides: Partial<AnalysisExecutionResult> = {}): AnalysisExecutionResult {
  return {
    correlationId: "an-abc123",
    investigationId: 7,
    reportName: "report.txt",
    riskScore: 42,
    severity: "high",
    status: "complete",
    existing: false,
    options: DEFAULT_ANALYSIS_OPTIONS,
    ...overrides,
  };
}

function fixtureError(): AnalysisExecutionError {
  return { kind: "unexpected", message: "Something went wrong.", cause: new Error("boom") };
}

describe("beginExecuting", () => {
  it("carries the ready input, its options, and the given runId into analyzing, with no correlation id or progress yet", () => {
    const ready = fixtureReady();
    const analyzing = beginExecuting(ready, "run-1");
    expect(analyzing).toEqual({
      status: "analyzing",
      input: ready.input,
      options: ready.options,
      runId: "run-1",
      correlationId: null,
      progress: null,
    });
  });

  it("carries a non-default options selection through unchanged", () => {
    const ready = updateOptions(fixtureReady(), IOCS_ONLY);
    const analyzing = beginExecuting(ready, "run-1");
    expect(analyzing.options).toEqual(IOCS_ONLY);
  });
});

describe("adoptCorrelationId", () => {
  it("sets the correlation id on a run that doesn't have one yet", () => {
    const analyzing = beginExecuting(fixtureReady(), "run-1");
    const adopted = adoptCorrelationId(analyzing, "an-xyz");
    expect(adopted.correlationId).toBe("an-xyz");
  });

  it("is a no-op once a correlation id has already been adopted", () => {
    const analyzing = adoptCorrelationId(beginExecuting(fixtureReady(), "run-1"), "an-first");
    const reAdopted = adoptCorrelationId(analyzing, "an-second");
    expect(reAdopted.correlationId).toBe("an-first");
  });
});

describe("updateProgress", () => {
  it("stores the given percent/message on the analyzing state", () => {
    const analyzing = beginExecuting(fixtureReady(), "run-1");
    const updated = updateProgress(analyzing, { percent: 40, message: "Extracting IOCs" });
    expect(updated.progress).toEqual({ percent: 40, message: "Extracting IOCs" });
  });

  it("overwrites a prior progress value with the latest one", () => {
    let analyzing = beginExecuting(fixtureReady(), "run-1");
    analyzing = updateProgress(analyzing, { percent: 20, message: "Extracting" });
    analyzing = updateProgress(analyzing, { percent: 80, message: "Scoring" });
    expect(analyzing.progress).toEqual({ percent: 80, message: "Scoring" });
  });
});

describe("markExecutionCompleted", () => {
  it("carries the input, runId, and the given result (including its applied options) into completed", () => {
    const ready = fixtureReady();
    const analyzing = beginExecuting(ready, "run-1");
    const result = fixtureResult({ options: IOCS_ONLY });
    const completed = markExecutionCompleted(analyzing, result);
    expect(completed).toEqual({
      status: "completed",
      input: ready.input,
      runId: "run-1",
      result,
    });
    expect(completed.result.options).toEqual(IOCS_ONLY);
  });
});

describe("markExecutionFailed", () => {
  it("carries the input, options, runId, and the given error into failed", () => {
    const ready = updateOptions(fixtureReady(), IOCS_ONLY);
    const analyzing = beginExecuting(ready, "run-1");
    const error = fixtureError();
    const failed = markExecutionFailed(analyzing, error);
    expect(failed).toEqual({
      status: "failed",
      input: ready.input,
      options: IOCS_ONLY,
      runId: "run-1",
      error,
    });
  });
});

describe("retryFailed", () => {
  it("returns to ready carrying the same input the failed run used", () => {
    const ready = fixtureReady();
    const analyzing = beginExecuting(ready, "run-1");
    const failed = markExecutionFailed(analyzing, fixtureError());
    const retried = retryFailed(failed);
    expect(retried).toEqual({ status: "ready", input: ready.input, options: ready.options });
    expect(retried.input).toBe(ready.input);
  });

  it("preserves the options the failed run was started with, unless the user changes them afterward", () => {
    const ready = updateOptions(fixtureReady(), IOCS_ONLY);
    const analyzing = beginExecuting(ready, "run-1");
    const failed = markExecutionFailed(analyzing, fixtureError());

    const retried = retryFailed(failed);
    expect(retried.options).toEqual(IOCS_ONLY);

    // The user is still free to change options after a retry lands
    // back on `ready`, same as any other ready state.
    const changed = updateOptions(retried, DEFAULT_ANALYSIS_OPTIONS);
    expect(changed.options).toEqual(DEFAULT_ANALYSIS_OPTIONS);
  });
});

describe("execution state shape invariants", () => {
  it("analyzing always carries the input it was started from", () => {
    const ready = fixtureReady();
    const analyzing = beginExecuting(ready, "run-1");
    expect(analyzing.input).toBe(ready.input);
  });

  it("completed cannot be reached without an execution result (constructor requires one)", () => {
    const analyzing = beginExecuting(fixtureReady(), "run-1");
    const completed = markExecutionCompleted(analyzing, fixtureResult());
    expect(completed.result).toBeDefined();
  });

  it("a stale run's completion does not carry the current run's identity", () => {
    const ready = fixtureReady();
    const staleRun = beginExecuting(ready, "run-old");
    const currentRun = beginExecuting(ready, "run-new");
    const staleCompletion = markExecutionCompleted(staleRun, fixtureResult());
    // The caller (useAnalysisExecution) is expected to compare
    // staleCompletion.runId against the *current* state's runId before
    // applying it — this test documents that the two are indeed
    // distinguishable data, which is what makes that guard possible.
    expect(staleCompletion.runId).not.toBe(currentRun.runId);
  });
});
