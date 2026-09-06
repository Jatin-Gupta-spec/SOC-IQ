/**
 * `AnalysisResultSummary` tests — Phase 4I-2 §15, extended Part 3
 * §8 for honest disabled-stage representation.
 *
 * `react-dom/server`'s `renderToStaticMarkup`, matching the project's
 * existing no-jsdom-by-default convention for pure presentational
 * components (see `pages.test.tsx`'s own header). No Router is
 * needed: the handoff control is a plain `<a href="#...">`, not a
 * `react-router` component (see `AnalyzePage.tsx`'s doc comment on
 * `INVESTIGATIONS_PATH` for why).
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnalysisResultSummary } from "./AnalysisResultSummary";
import { DEFAULT_ANALYSIS_OPTIONS } from "./analysisWorkflowState";
import type { AnalysisExecutionResult } from "./analysisWorkflowState";
import type { AnalysisOptions } from "../../shared/api/types";

const INVESTIGATIONS_PATH = "/investigations";

function fixtureResult(overrides: Partial<AnalysisExecutionResult> = {}): AnalysisExecutionResult {
  return {
    correlationId: "an-1",
    investigationId: 42,
    reportName: "phishing-attachment.eml",
    riskScore: 63,
    severity: "HIGH",
    status: "COMPLETED",
    existing: false,
    options: DEFAULT_ANALYSIS_OPTIONS,
    ...overrides,
  };
}

function render(result: AnalysisExecutionResult): string {
  return renderToStaticMarkup(
    <AnalysisResultSummary result={result} investigationsPath={INVESTIGATIONS_PATH} />,
  );
}

describe("AnalysisResultSummary", () => {
  it("renders without throwing for a typical result", () => {
    expect(() => render(fixtureResult())).not.toThrow();
  });

  it("renders the report name, risk score, severity, and status", () => {
    const html = render(fixtureResult());
    expect(html).toContain("phishing-attachment.eml");
    expect(html).toContain("63");
    expect(html).toContain("HIGH");
    expect(html).toContain("COMPLETED");
  });

  it("does not fabricate IOC or threat-intelligence data — only shows the boundary note", () => {
    const html = render(fixtureResult());
    expect(html).toContain("open the investigation below to see them in its IOCs and Threat Intel tabs");
    // No count/category vocabulary should appear anywhere — nothing
    // in `AnalysisExecutionResult` provides one, so none should be
    // invented.
    expect(html).not.toMatch(/\b\d+\s*(IPs|IP addresses|domains|URLs|hashes|emails|CVEs)\b/i);
  });

  it("renders an accessible, real link straight to that investigation's own workspace when an investigation id exists (MAX7-F-01)", () => {
    const html = render(fixtureResult({ investigationId: 7 }));
    expect(html).toContain('href="#/investigations/7"');
    expect(html).toContain(">Open Investigation<");
  });

  it("does not render a broken handoff link when no investigation id is available", () => {
    const html = render(fixtureResult({ investigationId: null }));
    expect(html).not.toContain("Open Investigation");
    expect(html).toContain("No investigation record is available");
  });

  it("surfaces the existing-report note only when the result says existing: true", () => {
    const freshHtml = render(fixtureResult({ existing: false }));
    expect(freshHtml).not.toContain("already analyzed previously");

    const existingHtml = render(fixtureResult({ existing: true }));
    expect(existingHtml).toContain("already analyzed previously");
  });

  it("handles a long report name and long numeric identifiers without overflowing markup assumptions", () => {
    const longName = `${"a".repeat(180)}.eml`;
    const html = render(
      fixtureResult({ reportName: longName, investigationId: 9007199254740991 }),
    );
    expect(html).toContain(longName);
  });

  it("falls back to a neutral tone for an unrecognized severity/status value rather than throwing or hiding it", () => {
    const html = render(fixtureResult({ severity: "unexpected-value", status: "weird-status" }));
    expect(html).toContain("unexpected-value");
    expect(html).toContain("weird-status");
    expect(html).toContain("status-badge--neutral");
  });

  it("matches severity/status case-insensitively against the known tone vocabulary", () => {
    const html = render(fixtureResult({ severity: "critical", status: "completed" }));
    expect(html).toContain("status-badge--critical");
    expect(html).toContain("status-badge--success");
  });

  it("produces no duplicate keys across renders with different results (no React key warnings)", () => {
    const results = [
      fixtureResult({ investigationId: 1 }),
      fixtureResult({ investigationId: null }),
      fixtureResult({ existing: true }),
    ];
    for (const result of results) {
      expect(() => render(result)).not.toThrow();
    }
  });

  describe("disabled-stage honesty (Part 3 §8)", () => {
    const IOCS_ONLY: AnalysisOptions = { extract_iocs: true, enrich_ti: false, score_risk: false };
    const NOTHING: AnalysisOptions = { extract_iocs: false, enrich_ti: false, score_risk: false };

    it("shows Ran/Skipped for each stage per the result's applied options, not the request", () => {
      const html = render(fixtureResult({ options: IOCS_ONLY }));
      // extract_iocs: true -> Ran; the other two: false -> Skipped.
      expect(html).toMatch(/Extract IOCs[\s\S]*?Ran/);
      expect(html).toMatch(/Enrich Threat Intelligence[\s\S]*?Skipped/);
      expect(html).toMatch(/Calculate Risk[\s\S]*?Skipped/);
    });

    it("does not display a fabricated risk score when score_risk was disabled (NOT_SCORED sentinel)", () => {
      const html = render(
        fixtureResult({ options: NOTHING, severity: "NOT_SCORED", riskScore: 0 }),
      );
      expect(html).not.toContain("Risk score");
      expect(html).not.toContain("NOT_SCORED");
      expect(html).toContain("Risk scoring was disabled for this run");
    });

    it("still shows a real risk score/severity when score_risk was enabled", () => {
      const html = render(fixtureResult({ options: DEFAULT_ANALYSIS_OPTIONS, severity: "HIGH", riskScore: 63 }));
      expect(html).toContain("Risk score");
      expect(html).toContain("63");
      expect(html).toContain("HIGH");
    });

    it("notes when IOC extraction and/or TI enrichment were disabled, without claiming they ran", () => {
      const iocsOnlyHtml = render(fixtureResult({ options: IOCS_ONLY }));
      expect(iocsOnlyHtml).toContain("Threat-intelligence enrichment was disabled for this run.");
      expect(iocsOnlyHtml).not.toContain("IOC extraction was disabled for this run.");

      const nothingHtml = render(fixtureResult({ options: NOTHING, severity: "NOT_SCORED", riskScore: 0 }));
      expect(nothingHtml).toContain(
        "IOC extraction and threat-intelligence enrichment were both disabled for this run.",
      );
    });

    it("shows no disabled-stage note at all when every stage ran", () => {
      const html = render(fixtureResult({ options: DEFAULT_ANALYSIS_OPTIONS }));
      expect(html).not.toContain("was disabled for this run");
    });
  });
});
