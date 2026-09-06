import { describe, expect, it } from "vitest";
import { normalizeReportsList } from "./reportsViewModel";
import type { InvestigationSummary } from "../../shared/api/types";

const COMPLETED: InvestigationSummary = {
  investigation_id: 42,
  report_name: "phishing-report.eml",
  risk_score: 87,
  severity: "HIGH",
  confidence: 0.91,
  status: "COMPLETED",
  analyzed_at: "2026-08-20T10:15:00",
};

const FAILED: InvestigationSummary = {
  investigation_id: 44,
  report_name: "corrupt-report.txt",
  risk_score: 0,
  severity: "NOT_SCORED",
  confidence: 0,
  status: "FAILED",
  analyzed_at: "2026-08-22T08:00:00",
};

const NULL_ID: InvestigationSummary = {
  investigation_id: null,
  report_name: "legacy-report.txt",
  risk_score: 10,
  severity: "LOW",
  confidence: 0.4,
  status: "COMPLETED",
  analyzed_at: "2026-08-01T00:00:00",
};

describe("normalizeReportsList", () => {
  it("returns an empty array for an empty input, never fabricated rows", () => {
    expect(normalizeReportsList([])).toEqual([]);
  });

  it("maps a real investigation to its real report row fields", () => {
    const row = normalizeReportsList([COMPLETED])[0]!;

    expect(row).toEqual({
      rowId: "42",
      investigationId: 42,
      reportName: "phishing-report.eml",
      status: "COMPLETED",
      statusTone: "success",
      analyzedAt: "2026-08-20T10:15:00",
      href: "#/investigations/42",
    });
  });

  it("reuses the existing statusTone mapping rather than redefining it", () => {
    const row = normalizeReportsList([FAILED])[0]!;
    expect(row.status).toBe("FAILED");
    expect(row.statusTone).toBe("error"); // "failed" -> error, per statusTone()
  });

  it("falls back to a position-qualified rowId and null href when investigation_id is null", () => {
    const row = normalizeReportsList([NULL_ID])[0]!;

    expect(row.investigationId).toBeNull();
    expect(row.rowId).toBe("unidentified-0");
    expect(row.href).toBeNull();
  });

  it("does not carry severity/risk/confidence -- those remain InvestigationsPage's own columns", () => {
    const row = normalizeReportsList([COMPLETED])[0]!;
    expect(row).not.toHaveProperty("severity");
    expect(row).not.toHaveProperty("riskScore");
    expect(row).not.toHaveProperty("confidenceLabel");
  });

  it("maps a full list preserving order and per-row correctness", () => {
    const rows = normalizeReportsList([COMPLETED, FAILED, NULL_ID]);

    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.reportName)).toEqual([
      "phishing-report.eml",
      "corrupt-report.txt",
      "legacy-report.txt",
    ]);
  });
});
