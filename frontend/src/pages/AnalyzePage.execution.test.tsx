// @vitest-environment jsdom
/**
 * `AnalyzePage` execution/result/handoff tests — Phase 4I-2 §15.
 *
 * Complements `pages.test.tsx` (static-markup, idle-state-only,
 * frozen-4G-2 shared page assertions) and `useAnalysisExecution.test.tsx`
 * (the hook's own state-machine logic in isolation). This file drives
 * the real, composed `AnalyzePage` — real `FileDropzone`, real
 * `analysisInput` validation, real `useAnalysisExecution` wiring —
 * through an actual file selection, mocking only the two boundaries
 * `useAnalysisExecution.test.tsx` already establishes as the correct
 * seam for deterministic tests: `analysisExecution.ts` (so completion/
 * failure is controllable) and `analysisReportPath.ts` (so `canStart`
 * isn't permanently blocked by the honest "no filesystem capability"
 * gap — see that module's own doc comment). No `Router` is mounted,
 * matching `pages.test.tsx`'s existing no-Router convention: the
 * investigation handoff is a plain `<a href="#...">`, not a
 * `react-router` component, specifically so this remains possible.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const executeAnalysisMock = vi.fn();
vi.mock("./analyze/analysisExecution", () => ({
  executeAnalysis: (...args: unknown[]) => executeAnalysisMock(...args),
}));

vi.mock("./analyze/analysisReportPath", () => ({
  resolveReportPath: () => ({ ok: true, reportPath: "/tmp/report.txt" }),
  describeReportPathBlockedReason: () => "blocked",
}));

vi.mock("../shared/events/eventSourceManager", () => ({
  subscribe: () => () => {},
}));

import { AnalyzePage } from "./AnalyzePage";
import { DEFAULT_ANALYSIS_OPTIONS } from "./analyze/analysisWorkflowState";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  executeAnalysisMock.mockReset();
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

async function renderAndReachReady(): Promise<void> {
  act(() => {
    root = createRoot(container);
    root.render(<AnalyzePage />);
  });

  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["report body"], "report.txt", { type: "text/plain" });
  // A minimal `FileList`-like stub (`length` + a numeric `item()`),
  // matching `FileDropzone.live.test.tsx`'s own approach — jsdom does
  // not let a real `FileList` be constructed directly, and the
  // component only ever reads `.length`/`.item()` (`handleFiles`).
  const fileList = { length: 1, item: (index: number) => (index === 0 ? file : null) };
  Object.defineProperty(input, "files", { value: fileList, configurable: true });

  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
    // Let the async `validateAnalysisInput` boundary resolve.
    await Promise.resolve();
    await Promise.resolve();
  });
}

function clickStart(): void {
  const button = Array.from(container.querySelectorAll("button")).find(
    (candidate) => candidate.textContent === "Start Analysis",
  );
  expect(button).toBeTruthy();
  act(() => {
    button?.click();
  });
}

describe("AnalyzePage completed result", () => {
  it("renders the result summary and a real investigation handoff link once analysis completes", async () => {
    let resolveExecution: (value: unknown) => void = () => {};
    executeAnalysisMock.mockReturnValue(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );

    await renderAndReachReady();
    clickStart();

    await act(async () => {
      resolveExecution({
        ok: true,
        result: {
          correlationId: "an-1",
          investigationId: 9,
          reportName: "report.txt",
          riskScore: 82,
          severity: "CRITICAL",
          status: "COMPLETED",
          existing: false,
          options: DEFAULT_ANALYSIS_OPTIONS,
        },
      });
      await Promise.resolve();
    });

    const link = container.querySelector("a") as HTMLAnchorElement | null;
    expect(link).toBeTruthy();
    expect(link?.getAttribute("href")).toBe("#/investigations/9");
    expect(link?.textContent).toBe("Open Investigation");
    expect(container.textContent).toContain("82");
    expect(container.textContent).toContain("CRITICAL");
  });

  it("does not render an investigation handoff link when investigationId is null", async () => {
    let resolveExecution: (value: unknown) => void = () => {};
    executeAnalysisMock.mockReturnValue(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );

    await renderAndReachReady();
    clickStart();

    await act(async () => {
      resolveExecution({
        ok: true,
        result: {
          correlationId: "an-1",
          investigationId: null,
          reportName: "report.txt",
          riskScore: 10,
          severity: "LOW",
          status: "COMPLETED",
          existing: false,
          options: DEFAULT_ANALYSIS_OPTIONS,
        },
      });
      await Promise.resolve();
    });

    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("No investigation record is available");
  });
});

describe("AnalyzePage failure + retry", () => {
  it("shows a Try Again control on failure, and retrying re-invokes execution and can reach completed", async () => {
    let firstResolve: (value: unknown) => void = () => {};
    let secondResolve: (value: unknown) => void = () => {};
    executeAnalysisMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          firstResolve = resolve;
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          secondResolve = resolve;
        }),
      );

    await renderAndReachReady();
    clickStart();

    await act(async () => {
      firstResolve({
        ok: false,
        error: { kind: "application_failure", message: "Analysis failed while processing this report.", cause: new Error("x") },
      });
      await Promise.resolve();
    });

    expect(container.textContent).toContain("Analysis failed while processing this report.");
    const retryButton = Array.from(container.querySelectorAll("button")).find(
      (candidate) => candidate.textContent === "Try Again",
    );
    expect(retryButton).toBeTruthy();
    expect(retryButton?.disabled).toBe(false);

    await act(async () => {
      retryButton?.click();
    });

    expect(executeAnalysisMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      secondResolve({
        ok: true,
        result: {
          correlationId: "an-2",
          investigationId: 3,
          reportName: "report.txt",
          riskScore: 20,
          severity: "MEDIUM",
          status: "COMPLETED",
          existing: false,
          options: DEFAULT_ANALYSIS_OPTIONS,
        },
      });
      await Promise.resolve();
    });

    expect(container.textContent).toContain("20");
  });
});

function findCheckbox(name: "extract_iocs" | "enrich_ti" | "score_risk"): HTMLInputElement {
  const id =
    name === "extract_iocs"
      ? "analysis-option-extract-iocs"
      : name === "enrich_ti"
        ? "analysis-option-enrich-ti"
        : "analysis-option-score-risk";
  const checkbox = container.querySelector(`#${id}`) as HTMLInputElement | null;
  expect(checkbox).toBeTruthy();
  return checkbox as HTMLInputElement;
}

describe("AnalyzePage options controls (Part 3 §4/§5/§6)", () => {
  it("renders all three options, all checked by default", async () => {
    await renderAndReachReady();

    expect(findCheckbox("extract_iocs").checked).toBe(true);
    expect(findCheckbox("enrich_ti").checked).toBe(true);
    expect(findCheckbox("score_risk").checked).toBe(true);
  });

  it("unchecking Extract IOCs changes the actual analyze_report payload", async () => {
    executeAnalysisMock.mockReturnValue(new Promise(() => {}));
    await renderAndReachReady();

    act(() => {
      findCheckbox("extract_iocs").click();
    });
    expect(findCheckbox("extract_iocs").checked).toBe(false);

    clickStart();

    expect(executeAnalysisMock).toHaveBeenCalledWith("/tmp/report.txt", {
      extract_iocs: false,
      enrich_ti: true,
      score_risk: true,
    });
  });

  it("unchecking Enrich Threat Intelligence changes the actual analyze_report payload", async () => {
    executeAnalysisMock.mockReturnValue(new Promise(() => {}));
    await renderAndReachReady();

    act(() => {
      findCheckbox("enrich_ti").click();
    });
    clickStart();

    expect(executeAnalysisMock).toHaveBeenCalledWith("/tmp/report.txt", {
      extract_iocs: true,
      enrich_ti: false,
      score_risk: true,
    });
  });

  it("unchecking Calculate Risk changes the actual analyze_report payload", async () => {
    executeAnalysisMock.mockReturnValue(new Promise(() => {}));
    await renderAndReachReady();

    act(() => {
      findCheckbox("score_risk").click();
    });
    clickStart();

    expect(executeAnalysisMock).toHaveBeenCalledWith("/tmp/report.txt", {
      extract_iocs: true,
      enrich_ti: true,
      score_risk: false,
    });
  });

  it("options remain selected once execution starts (ready -> analyzing)", async () => {
    executeAnalysisMock.mockReturnValue(new Promise(() => {}));
    await renderAndReachReady();

    act(() => {
      findCheckbox("enrich_ti").click();
    });
    clickStart();

    expect(findCheckbox("enrich_ti").checked).toBe(false);
    expect(findCheckbox("extract_iocs").checked).toBe(true);
  });

  it("disables the controls while analyzing, but keeps showing the selection", async () => {
    executeAnalysisMock.mockReturnValue(new Promise(() => {}));
    await renderAndReachReady();

    act(() => {
      findCheckbox("score_risk").click();
    });
    clickStart();

    expect(findCheckbox("score_risk").disabled).toBe(true);
    expect(findCheckbox("score_risk").checked).toBe(false);
  });

  it("retry preserves the selected options unless the user changes them", async () => {
    let firstResolve: (value: unknown) => void = () => {};
    let secondResolve: (value: unknown) => void = () => {};
    executeAnalysisMock
      .mockReturnValueOnce(
        new Promise((resolve) => {
          firstResolve = resolve;
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          secondResolve = resolve;
        }),
      );

    await renderAndReachReady();
    act(() => {
      findCheckbox("enrich_ti").click();
    });
    clickStart();

    await act(async () => {
      firstResolve({
        ok: false,
        error: { kind: "application_failure", message: "Analysis failed.", cause: new Error("x") },
      });
      await Promise.resolve();
    });

    const retryButton = Array.from(container.querySelectorAll("button")).find(
      (candidate) => candidate.textContent === "Try Again",
    );
    await act(async () => {
      retryButton?.click();
    });

    expect(executeAnalysisMock).toHaveBeenNthCalledWith(2, "/tmp/report.txt", {
      extract_iocs: true,
      enrich_ti: false,
      score_risk: true,
    });

    secondResolve({
      ok: true,
      result: {
        correlationId: "an-2",
        investigationId: 3,
        reportName: "report.txt",
        riskScore: 20,
        severity: "MEDIUM",
        status: "COMPLETED",
        existing: false,
        options: { extract_iocs: true, enrich_ti: false, score_risk: true },
      },
    });
  });
});

describe("AnalyzePage disabled-stage result honesty (Part 3 §8)", () => {
  it("does not display a fabricated risk score when score_risk was disabled server-side", async () => {
    let resolveExecution: (value: unknown) => void = () => {};
    executeAnalysisMock.mockReturnValue(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );

    await renderAndReachReady();
    act(() => {
      findCheckbox("score_risk").click();
    });
    clickStart();

    await act(async () => {
      resolveExecution({
        ok: true,
        result: {
          correlationId: "an-1",
          investigationId: 9,
          reportName: "report.txt",
          riskScore: 0,
          severity: "NOT_SCORED",
          status: "COMPLETED",
          existing: false,
          options: { extract_iocs: true, enrich_ti: true, score_risk: false },
        },
      });
      await Promise.resolve();
    });

    expect(container.textContent).not.toContain("NOT_SCORED");
    expect(container.textContent).toContain("Risk scoring was disabled for this run");
  });

  it("does not claim TI enrichment ran when enrich_ti was disabled server-side", async () => {
    let resolveExecution: (value: unknown) => void = () => {};
    executeAnalysisMock.mockReturnValue(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );

    await renderAndReachReady();
    act(() => {
      findCheckbox("enrich_ti").click();
    });
    clickStart();

    await act(async () => {
      resolveExecution({
        ok: true,
        result: {
          correlationId: "an-1",
          investigationId: 9,
          reportName: "report.txt",
          riskScore: 12,
          severity: "LOW",
          status: "COMPLETED",
          existing: false,
          options: { extract_iocs: true, enrich_ti: false, score_risk: true },
        },
      });
      await Promise.resolve();
    });

    expect(container.textContent).toContain("Threat-intelligence enrichment was disabled for this run.");
  });

  it("does not claim IOC extraction ran when extract_iocs was disabled server-side", async () => {
    let resolveExecution: (value: unknown) => void = () => {};
    executeAnalysisMock.mockReturnValue(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );

    await renderAndReachReady();
    act(() => {
      findCheckbox("extract_iocs").click();
    });
    clickStart();

    await act(async () => {
      resolveExecution({
        ok: true,
        result: {
          correlationId: "an-1",
          investigationId: 9,
          reportName: "report.txt",
          riskScore: 12,
          severity: "LOW",
          status: "COMPLETED",
          existing: false,
          options: { extract_iocs: false, enrich_ti: true, score_risk: true },
        },
      });
      await Promise.resolve();
    });

    expect(container.textContent).toContain("IOC extraction was disabled for this run.");
  });
});
