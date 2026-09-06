import { describe, expect, it } from "vitest";
import { normalizeInvestigationsList } from "./investigationsViewModel";
import type { InvestigationSummary } from "../../shared/api/types";

const SCORED: InvestigationSummary = {
  investigation_id: 42,
  report_name: "phishing-report.eml",
  risk_score: 87,
  severity: "HIGH",
  confidence: 0.91,
  status: "COMPLETED",
  analyzed_at: "2026-08-20T10:15:00",
};

const NOT_SCORED: InvestigationSummary = {
  investigation_id: 43,
  report_name: "unscored-report.txt",
  risk_score: 0,
  severity: "NOT_SCORED",
  confidence: 0,
  status: "COMPLETED",
  analyzed_at: "2026-08-21T11:00:00",
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

describe("normalizeInvestigationsList", () => {
  it("returns an empty array for an empty input, never fabricated rows", () => {
    expect(normalizeInvestigationsList([])).toEqual([]);
  });

  it("maps a real scored investigation to its real row fields", () => {
    const row = normalizeInvestigationsList([SCORED])[0]!;

    expect(row).toMatchObject({
      rowId: "42",
      investigationId: 42,
      reportName: "phishing-report.eml",
      status: "COMPLETED",
      scored: true,
      severity: "HIGH",
      riskScore: 87,
      confidenceLabel: "91%",
      analyzedAt: "2026-08-20T10:15:00",
      href: "#/investigations/42",
    });
  });

  it("severity/status tones reuse the existing InvestigationHeaderCard mapping", () => {
    const row = normalizeInvestigationsList([SCORED])[0]!;
    expect(row.severityTone).toBe("error"); // "high" -> error, per severityTone()
    expect(row.statusTone).toBe("success"); // "completed" -> success, per statusTone()
  });

  it("treats the NOT_SCORED sentinel honestly -- no fabricated risk/confidence", () => {
    const row = normalizeInvestigationsList([NOT_SCORED])[0]!;

    expect(row.scored).toBe(false);
    expect(row.severity).toBe("Not scored");
    expect(row.severityTone).toBe("neutral");
    expect(row.riskScore).toBeNull();
    expect(row.confidenceLabel).toBeNull();
  });

  it("falls back to a position-qualified rowId and null href when investigation_id is null", () => {
    const row = normalizeInvestigationsList([NULL_ID])[0]!;

    expect(row.investigationId).toBeNull();
    expect(row.rowId).toBe("unidentified-0");
    expect(row.href).toBeNull();
  });

  it("maps a full list preserving order and per-row correctness", () => {
    const rows = normalizeInvestigationsList([SCORED, NOT_SCORED, NULL_ID]);

    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.reportName)).toEqual([
      "phishing-report.eml",
      "unscored-report.txt",
      "legacy-report.txt",
    ]);
  });
});
