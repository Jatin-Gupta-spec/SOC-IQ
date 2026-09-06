/**
 * Focused tests for `executeAnalysis()` — mocks `runCommand` (the
 * real typed command client), per §18's "deterministic fixtures
 * where live backend execution cannot run ... do NOT fake a
 * successful backend call and call it integration testing"; this
 * mocks the boundary this module itself calls, not the HTTP/backend
 * layer underneath it.
 *
 * Part 3: `executeAnalysis` now takes and sends `options`
 * (`AnalysisOptions`) alongside `report_path`, and maps the
 * backend's echoed-back `options` onto the typed result — these
 * tests cover both.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

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
import { executeAnalysis } from "./analysisExecution";
import type { AnalysisOptions } from "../../shared/api/types";

const ALL_ENABLED: AnalysisOptions = { extract_iocs: true, enrich_ti: true, score_risk: true };
const IOCS_ONLY: AnalysisOptions = { extract_iocs: true, enrich_ti: false, score_risk: false };

describe("executeAnalysis", () => {
  afterEach(() => {
    runCommandMock.mockReset();
  });

  it("calls the real analyze_report command with the given report path and options", async () => {
    runCommandMock.mockResolvedValue({
      correlation_id: "an-abc123",
      existing: false,
      investigation: {
        investigation_id: 7,
        report_name: "report.txt",
        risk_score: 42,
        severity: "high",
        confidence: 0.9,
        status: "complete",
        analyzed_at: "2026-08-26T00:00:00",
      },
      options: ALL_ENABLED,
    });

    await executeAnalysis("/tmp/report.txt", ALL_ENABLED);

    expect(runCommandMock).toHaveBeenCalledWith("analyze_report", {
      report_path: "/tmp/report.txt",
      options: ALL_ENABLED,
    });
  });

  it("sends a partial selection through unchanged, not merged with defaults", async () => {
    runCommandMock.mockResolvedValue({
      correlation_id: "an-abc123",
      existing: false,
      investigation: {
        investigation_id: 7,
        report_name: "report.txt",
        risk_score: 0,
        severity: "unknown",
        confidence: 0,
        status: "complete",
        analyzed_at: "2026-08-26T00:00:00",
      },
      options: IOCS_ONLY,
    });

    await executeAnalysis("/tmp/report.txt", IOCS_ONLY);

    expect(runCommandMock).toHaveBeenCalledWith("analyze_report", {
      report_path: "/tmp/report.txt",
      options: IOCS_ONLY,
    });
  });

  it("maps a successful response to a typed AnalysisExecutionResult, including the applied options", async () => {
    runCommandMock.mockResolvedValue({
      correlation_id: "an-abc123",
      existing: true,
      investigation: {
        investigation_id: 7,
        report_name: "report.txt",
        risk_score: 42,
        severity: "high",
        confidence: 0.9,
        status: "complete",
        analyzed_at: "2026-08-26T00:00:00",
      },
      options: IOCS_ONLY,
    });

    const outcome = await executeAnalysis("/tmp/report.txt", ALL_ENABLED);

    expect(outcome).toEqual({
      ok: true,
      result: {
        correlationId: "an-abc123",
        investigationId: 7,
        reportName: "report.txt",
        riskScore: 42,
        severity: "high",
        status: "complete",
        existing: true,
        options: IOCS_ONLY,
      },
    });
  });

  it("maps a rejected command call to a typed failure outcome rather than throwing", async () => {
    runCommandMock.mockRejectedValue(
      new CommandFailedError("analyze_report", "REPORT_NOT_FOUND", "No report at /tmp/missing.txt."),
    );

    const outcome = await executeAnalysis("/tmp/missing.txt", ALL_ENABLED);

    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(outcome.error.kind).toBe("invalid_input");
    }
  });

  it("never throws, even for an unrecognized rejection value", async () => {
    runCommandMock.mockRejectedValue("not an Error instance");

    await expect(executeAnalysis("/tmp/report.txt", ALL_ENABLED)).resolves.toMatchObject({ ok: false });
  });
});
